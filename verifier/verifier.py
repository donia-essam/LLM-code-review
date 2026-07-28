import json
from pathlib import Path
from typing import Optional

try:
    from .ast_checker import verify_entity
    from .static_checker import verify_claim
except ImportError:
    from ast_checker import verify_entity
    from static_checker import verify_claim


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


def find_source_file(file_name: str, claim: str) -> Optional[Path]:
    """
    Locate the source file inside the dataset corresponding
    to the reported bug class.

    The verifier does not fall back to clean or unrelated datasets,
    because that could verify the claim against the wrong file version.
    """

    claim_directories = {
        "unused_variable": DATA_ROOT / "mutated",
        "null_safety_violation": DATA_ROOT / "mutated_null",
        "off_by_one_bound": DATA_ROOT / "mutated_offbyone",
    }

    search_root = claim_directories.get(claim)

    if search_root is None:
        return None

    if not search_root.exists():
        return None

    matches = list(search_root.rglob(file_name))

    if len(matches) == 1:
        return matches[0]

    if len(matches) == 0:
        return None

    # Ambiguous: more than one file with the same name.
    print(
        f"[Warning] Ambiguous file '{file_name}': "
        f"{len(matches)} matches found inside '{search_root.name}'."
    )

    return None


def read_source_code(path: Path) -> str:
    """Read a Python source file."""
    return path.read_text(encoding="utf-8")


def verify_comment(comment: dict) -> dict:
    """Verify one LLM-generated code review comment."""

    file_name = comment.get("file", "")
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

    source_path = find_source_file(file_name, claim)

    if source_path is None:
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

    # Stage 2: Static-analysis cross-check
    static_result = verify_claim(
        code=code,
        entity=entity,
        claim=claim,
    )

    entity_exists = ast_result["entity_exists"]
    line_match = ast_result["entity_at_line"]

    # Final classification
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