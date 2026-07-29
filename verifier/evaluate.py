import ast
import json
from pathlib import Path
from difflib import SequenceMatcher

try:
    from .verifier import verify_comment
except ImportError:
    from verifier import verify_comment


PROJECT_ROOT = Path(__file__).resolve().parent.parent

GROUND_TRUTH_FILE = (
    PROJECT_ROOT
    / "code_review_project"
    / "ground_truth"
    / "injection_log.json"
)

OUTPUT_FILE = PROJECT_ROOT / "evaluation_results.json"


BUG_TYPE_MAP = {
    "unused_variable": "unused_variable",
    "unused_temp": "unused_variable",
    "null_safety": "null_safety_violation",
    "off_by_one": "off_by_one_bound",
}


def load_ground_truth() -> list[dict]:
    with GROUND_TRUTH_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("injection_log.json must contain a list.")

    return data


def normalize_bug_type(bug_type: str) -> str | None:
    return BUG_TYPE_MAP.get(bug_type)


def get_changed_lines(original: str, mutated: str) -> list[str]:
    """Return lines added or replaced by the mutation."""

    original_lines = original.splitlines()
    mutated_lines = mutated.splitlines()

    matcher = SequenceMatcher(
        None,
        original_lines,
        mutated_lines,
        autojunk=False,
    )

    changed = []

    for tag, _, _, j1, j2 in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            changed.extend(mutated_lines[j1:j2])

    return changed


def extract_unused_entity(changed_lines: list[str]) -> str | None:
    for line in changed_lines:
        try:
            tree = ast.parse(line.strip())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and node.targets
                and isinstance(node.targets[0], ast.Name)
            ):
                return node.targets[0].id

    return None


def extract_null_entity(changed_lines: list[str]) -> str | None:
    """
    Find a method/attribute dereference introduced by
    the null-safety mutation.
    """

    for line in changed_lines:
        try:
            tree = ast.parse(line.strip())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                try:
                    return ast.unparse(node)
                except Exception:
                    continue

            if isinstance(node, ast.Attribute):
                try:
                    return ast.unparse(node)
                except Exception:
                    continue

    return None


def extract_off_by_one_entity(
    original_code: str,
    mutated_code: str,
) -> str | None:
    """
    Find a range(...) expression that exists in the mutated
    code but not in the original code.
    """

    try:
        original_tree = ast.parse(original_code)
        mutated_tree = ast.parse(mutated_code)
    except SyntaxError:
        return None

    def get_ranges(tree: ast.AST) -> list[str]:
        ranges = []

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "range"
            ):
                try:
                    ranges.append(ast.unparse(node))
                except Exception:
                    pass

        return ranges

    original_ranges = get_ranges(original_tree)
    mutated_ranges = get_ranges(mutated_tree)

    # Find range expressions introduced by the mutation.
    remaining_original = original_ranges.copy()

    for mutated_range in mutated_ranges:
        if mutated_range in remaining_original:
            remaining_original.remove(mutated_range)
        else:
            return mutated_range

    return None


def extract_entity(
    original_code: str,
    mutated_code: str,
    claim: str,
    line_number: int,
) -> str | None:

    changed_lines = get_changed_lines(
        original_code,
        mutated_code,
    )

    if claim == "unused_variable":
        return extract_unused_entity(changed_lines)

    if claim == "null_safety_violation":
        return extract_null_entity(changed_lines)

    if claim == "off_by_one_bound":
        return extract_off_by_one_entity(
            original_code,
            mutated_code,
        )

    return None


def run_evaluation() -> dict:
    records = load_ground_truth()

    results = []

    grounded = 0
    hallucinated = 0
    hallucinated_by_type = {}
    extraction_failed = 0
    extraction_failed_by_type = {}
    other_status = 0

    for record in records:

        claim = normalize_bug_type(
            record.get("bug_type", "")
        )

        if claim is None:
            continue

        original_code = record.get("original_code", "")
        mutated_code = record.get("mutated_code", "")

        entity = extract_entity(
        original_code,
        mutated_code,
        claim,
        record.get("line", 0),
        )

        evaluation_item = {
            "file": record.get("file"),
            "line": record.get("line"),
            "bug_type": record.get("bug_type"),
            "claim": claim,
            "entity": entity,
            "expected": "grounded",
        }

        if entity is None:
            evaluation_item["status"] = "entity_extraction_failed"
            extraction_failed += 1

            bug_type = record.get("bug_type", "unknown")
            extraction_failed_by_type[bug_type] = (
            extraction_failed_by_type.get(bug_type, 0) + 1
            )

            results.append(evaluation_item)
            continue

        comment = {
            "file": Path(record["file"]).name,
            "line": record["line"],
            "entity": entity,
            "claim": claim,
        }

        verifier_result = verify_comment(comment)

        status = verifier_result["status"]

        evaluation_item["status"] = status
        evaluation_item["verifier_result"] = verifier_result

        if status == "grounded":
            grounded += 1

        elif status == "hallucinated":
            hallucinated += 1

            bug_type = record.get("bug_type", "unknown")
            hallucinated_by_type[bug_type] = (
                hallucinated_by_type.get(bug_type, 0) + 1
            )

        else:
            other_status += 1

        results.append(evaluation_item)

    evaluated = grounded + hallucinated

    positive_recall = (
        grounded / evaluated
        if evaluated > 0
        else 0.0
    )

    output = {
        "summary": {
            "ground_truth_records": len(records),
            "grounded": grounded,
            "hallucinated": hallucinated,
            "hallucinated_by_type": hallucinated_by_type,
            "entity_extraction_failed": extraction_failed,
            "extraction_failed_by_type": extraction_failed_by_type,
            "other_status": other_status,
            "positive_recall": round(positive_recall, 4),
        },
        "results": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    return output


if __name__ == "__main__":
    try:
        output = run_evaluation()
        summary = output["summary"]

        print("\nEvaluation completed.")
        print(
            f"Ground-truth records: "
            f"{summary['ground_truth_records']}"
        )
        print(f"Grounded: {summary['grounded']}")
        print(f"Hallucinated: {summary['hallucinated']}")
        
        print(
            f"Hallucinated by type: "
            f"{summary['hallucinated_by_type']}"
        )
        print(
            f"Entity extraction failed: "
            f"{summary['entity_extraction_failed']}"
        )
        print(
            f"Other status: "
            f"{summary['other_status']}"
        )

        print(
            f"Extraction failures by type: "
            f"{summary['extraction_failed_by_type']}"
        )
        print(
            f"Positive recall: "
            f"{summary['positive_recall']:.2%}"
        )

        print(f"\nResults saved to: {OUTPUT_FILE}")

    except Exception as error:
        print(f"[Evaluation Error] {error}")