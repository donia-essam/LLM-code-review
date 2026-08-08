import json
from pathlib import Path
from typing import Optional

try:
    from .ast_checker import (
        verify_entity,
        verify_entity_nearby_line,
    )
    from .static_checker import verify_claim
    from .offbyone_reference_checker import reference_check
except ImportError:
    from ast_checker import (
        verify_entity,
        verify_entity_nearby_line,
    )
    from static_checker import verify_claim
    from offbyone_reference_checker import reference_check

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVIEW_RESULTS = PROJECT_ROOT / "review_results.json"
DATA_ROOT = PROJECT_ROOT / "code_review_project" / "data"
OUTPUT_FILE = PROJECT_ROOT / "verification_results.json"


def load_review_results() -> list[dict]:
    """Load the LLM code-review claims produced by the review agent."""
    if not REVIEW_RESULTS.exists():
        raise FileNotFoundError(
            f"Review results file not found: {REVIEW_RESULTS}"
        )

    with REVIEW_RESULTS.open("r", encoding="utf-8") as file:
        data = json.load(file)

    comments = data.get("comments")

    if not isinstance(comments, list):
        raise ValueError(
            "review_results.json must contain a 'comments' list."
        )

    return comments


def find_source_file(file_path: str, claim: str) -> Optional[Path]:
    """
    Locate the exact source file inside the dataset.

    Uses the full relative file path instead of only the basename,
    so duplicate filenames such as combination_sum.py are handled
    correctly.
    """

    claim_datasets = {
        "unused_variable": "mutated",
        "null_safety_violation": "mutated_null",
        "off_by_one_bound": "mutated_offbyone",
    }

    dataset = claim_datasets.get(claim)

    if dataset is None:
        return None

    normalized = file_path.replace("\\", "/")
    parts = normalized.split("/")

    if dataset not in parts:
        return None

    dataset_index = parts.index(dataset)

    relative_parts = parts[dataset_index + 1:]

    if not relative_parts:
        return None

    candidate = DATA_ROOT / dataset / Path(*relative_parts)

    if candidate.exists() and candidate.is_file():
        return candidate

    return None


def read_source_code(path: Path) -> str:
    """Read a Python source file."""
    return path.read_text(encoding="utf-8")


def verify_comment(
        comment: dict,
        source_path: Optional[Path] = None,
    ) -> dict:

    file_path = comment.get("file", "")
    file_name = Path(file_path).name
    entity = comment.get("entity", "")
    claim = comment.get("claim", "")
    line = comment.get("line", 0)

    result = {
        "file": file_name,
        "line": line,
        "entity": entity,
        "claim": claim,
    }

    # Basic schema validation
    if (
        not isinstance(file_name, str)
        or not file_name
        or not isinstance(entity, str)
        or not entity
        or not isinstance(claim, str)
        or not isinstance(line, int)
        or line < 1
    ):
        result.update({
            "status": "invalid_input",
            "ast_entity_exists": False,
            "ast_line_match": False,
            "static_check": False,
        })
        return result

    if source_path is None:
        source_path = find_source_file(file_path, claim)

    if source_path is None or not source_path.exists():
        result.update({
            "status": "file_not_found",
            "ast_entity_exists": False,
            "ast_line_match": False,
            "static_check": False,
        })
        return result

    code = read_source_code(source_path)

    # Stage 1: AST existence + line check
    ast_result = verify_entity(
        code=code,
        entity=entity,
        line=line,
    )

    if (
        claim == "off_by_one_bound"
        and not ast_result["entity_at_line"]
    ):
        ast_result["entity_at_line"] = verify_entity_nearby_line(
            code=code,
            entity=entity,
            line=line,
            max_distance=3,
 )
    # Stage 2: Static-analysis cross-check
    if claim == "off_by_one_bound":
        static_result = reference_check(
            file_path,
            entity,
            line,
        )
    else:
        static_result = verify_claim(
            code=code,
            entity=entity,
            claim=claim,
            line=line,
        )
    entity_exists = ast_result["entity_exists"]
    line_match = ast_result["entity_at_line"]

        # Final classification
    if claim == "off_by_one_bound":
        # For off-by-one claims, the reported entity may be
        # a contextual variable/function rather than the exact
        # AST expression containing the boundary mutation.
        #
        # The static checker is responsible for confirming
        # the actual boundary mutation.
        if static_result:
            status = "grounded"
        else:
            status = "hallucinated"
    else:
        # For other claim types, keep the strict AST + static
        # grounding requirements.
        if entity_exists and line_match and static_result:
            status = "grounded"
        else:
            status = "hallucinated"

    result.update({
        "resolved_file": str(
            source_path.relative_to(PROJECT_ROOT)
        ),
        "valid_syntax": ast_result["valid_syntax"],
        "ast_entity_exists": entity_exists,
        "ast_line_match": line_match,
        "static_check": static_result,
        "status": status,
    })

    return result


def run_verifier() -> dict:
    """Run verification over all LLM review comments."""

    comments = load_review_results()

    results = [
        verify_comment(comment)
        for comment in comments
    ]

    summary = {
        "total": len(results),
        "grounded": sum(
            result["status"] == "grounded"
            for result in results
        ),
        "hallucinated": sum(
            result["status"] == "hallucinated"
            for result in results
        ),
        "file_not_found": sum(
            result["status"] == "file_not_found"
            for result in results
        ),
        "invalid_input": sum(
            result["status"] == "invalid_input"
            for result in results
        ),
    }

    output = {
        "summary": summary,
        "results": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return output


if __name__ == "__main__":
    try:
        output = run_verifier()

        print("\nVerification completed.")
        print(f"Total claims: {output['summary']['total']}")
        print(f"Grounded: {output['summary']['grounded']}")
        print(f"Hallucinated: {output['summary']['hallucinated']}")
        print(f"File not found: {output['summary']['file_not_found']}")
        print(f"Invalid input: {output['summary']['invalid_input']}")
        print(f"\nResults saved to: {OUTPUT_FILE}")

    except Exception as error:
        print(f"[Verifier Error] {error}")