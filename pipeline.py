import json
from pathlib import Path

from review_agent import review_python_code_with_gemini
from verifier.verifier import verify_comment


PROJECT_ROOT = Path(__file__).resolve().parent

REVIEW_RESULTS = PROJECT_ROOT / "review_results.json"
VERIFICATION_RESULTS = PROJECT_ROOT / "verification_results.json"


def run_pipeline(target_file: Path) -> dict:
    """
    Run the complete Proposed pipeline:

    Python source
        -> LLM review agent
        -> structured claims
        -> AST/static verifier
        -> grounded/hallucinated results
    """

    if not target_file.exists():
        raise FileNotFoundError(
            f"Target file not found: {target_file}"
        )

    code = target_file.read_text(encoding="utf-8")

    # Stage 1: LLM reviewer
    raw_response = review_python_code_with_gemini(
        target_file.name,
        code,
    )

    review_data = json.loads(raw_response)

    comments = review_data.get("comments")

    if not isinstance(comments, list):
        raise ValueError(
            "Review agent output must contain a 'comments' list."
        )

    with REVIEW_RESULTS.open("w", encoding="utf-8") as file:
        json.dump(review_data, file, indent=2)

    # Stage 2: Grounding verifier
    verification_results = [
        verify_comment(comment)
        for comment in comments
    ]

    summary = {
        "total": len(verification_results),
        "grounded": sum(
            result["status"] == "grounded"
            for result in verification_results
        ),
        "hallucinated": sum(
            result["status"] == "hallucinated"
            for result in verification_results
        ),
        "file_not_found": sum(
            result["status"] == "file_not_found"
            for result in verification_results
        ),
        "invalid_input": sum(
            result["status"] == "invalid_input"
            for result in verification_results
        ),
    }

    output = {
        "target_file": str(target_file),
        "review": review_data,
        "verification": {
            "summary": summary,
            "results": verification_results,
        },
    }

    with VERIFICATION_RESULTS.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(output, file, indent=2)

    return output


if __name__ == "__main__":
    target = (
        PROJECT_ROOT
        / "code_review_project"
        / "data"
        / "mutated"
        / "algorithms"
        / "array"
        / "delete_nth.py"
    )

    try:
        output = run_pipeline(target)

        print("\nPipeline completed.")
        print(
            f"Total claims: "
            f"{output['verification']['summary']['total']}"
        )
        print(
            f"Grounded: "
            f"{output['verification']['summary']['grounded']}"
        )
        print(
            f"Hallucinated: "
            f"{output['verification']['summary']['hallucinated']}"
        )

    except Exception as error:
        print(f"[Pipeline Error] {error}")