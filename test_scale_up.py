import json
from verifier.verifier import verify_comment
from pathlib import Path

with open("scale_up_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)


all_results = []

for run in data:
    file_path = run["file_path"]
    run_id = run["run_id"]
    comments = run["output"].get("comments", [])

    print(f"Processing: {file_path} | Run: {run_id}")

    for comment in comments:
        source_path = Path(file_path)

        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path

        comment_for_verification = dict(comment)
        comment_for_verification["file"] = file_path

        result = verify_comment(
            comment_for_verification,
            source_path=source_path,
        )

        result["file_path"] = file_path
        result["run_id"] = run_id

        all_results.append(result)


summary = {
    "total": len(all_results),
    "grounded": sum(
        r["status"] == "grounded"
        for r in all_results
    ),
    "hallucinated": sum(
        r["status"] == "hallucinated"
        for r in all_results
    ),
    "file_not_found": sum(
        r["status"] == "file_not_found"
        for r in all_results
    ),
    "invalid_input": sum(
        r["status"] == "invalid_input"
        for r in all_results
    ),
}


output = {
    "summary": summary,
    "results": all_results,
}


with open("scale_up_verification_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)


print("\nScale-up verification completed.")
print(f"Total claims: {summary['total']}")
print(f"Grounded: {summary['grounded']}")
print(f"Hallucinated: {summary['hallucinated']}")
print(f"File not found: {summary['file_not_found']}")
print(f"Invalid input: {summary['invalid_input']}")
print("Results saved to: scale_up_verification_results.json")