"""
validate_dataset.py

Cross-checks the review agent + verifier output against the injection log
(ground truth) to check how many "grounded" claims actually match the real
injected bugs, and lists which mutated files returned zero comments.

Usage:
    python validate_dataset.py

Expects (relative to repo root):
    code_review_project/ground_truth/injection_log.json
    scale_up_verification_results.json   (from mohamed-branch, or wherever
                                           the verifier output was saved)

Outputs:
    dataset_validation/audit_details.json
    dataset_validation/empty_files.json
"""

import json
import os

INJECTION_LOG_PATH = "code_review_project/ground_truth/injection_log.json"
VERIFIER_RESULTS_PATH = "scale_up_verification_results.json"
OUTPUT_DIR = "dataset_validation"

# The injection log and the verifier use different names for the same bug
# types. Map injection-log names -> verifier claim names.
TYPE_MAP = {
    "unused_variable": "unused_variable",
    "null_safety": "null_safety_violation",
    "off_by_one": "off_by_one_bound",
}

# How many lines apart a claim can be from the logged bug and still count
# as a match (LLMs sometimes point at a line just before/after the real one).
LINE_TOLERANCE = 2


def cat_and_base(path):
    """Extract the dataset category (e.g. 'mutated_null') and the base
    filename from a path, regardless of slash direction."""
    p = path.replace("\\", "/")
    parts = p.split("/")
    try:
        idx = parts.index("data")
        cat = parts[idx + 1]
    except ValueError:
        cat = None
    return cat, os.path.basename(p)


def main():
    with open(INJECTION_LOG_PATH) as f:
        injections = json.load(f)

    with open(VERIFIER_RESULTS_PATH) as f:
        verifier_output = json.load(f)
    verif_results = verifier_output["results"]

    # Build a lookup: (category, filename) -> injection log entry
    injections_by_key = {}
    for entry in injections:
        cat, base = cat_and_base(entry["file"])
        injections_by_key.setdefault(cat, {})[base] = entry

    # --- Find files that never received any comment ---
    files_with_claims = {}
    for r in verif_results:
        cat, base = cat_and_base(r["resolved_file"])
        files_with_claims.setdefault(cat, set()).add(base)

    empty_files = {}
    for cat, entries in injections_by_key.items():
        all_files = set(entries.keys())
        has_claim = files_with_claims.get(cat, set())
        empty_files[cat] = sorted(all_files - has_claim)

    # --- Check each grounded claim against the injection log ---
    true_positives = 0
    grounded_total = 0
    mismatches = []
    no_entry_claims = []

    for r in verif_results:
        if r["status"] != "grounded":
            continue
        grounded_total += 1

        cat, base = cat_and_base(r["resolved_file"])
        logged_entry = injections_by_key.get(cat, {}).get(base)

        if logged_entry is None:
            no_entry_claims.append({
                "file": r["file"],
                "resolved_file": r["resolved_file"],
                "line": r["line"],
                "claim": r["claim"],
            })
            continue

        line_close = abs(logged_entry["line"] - r["line"]) <= LINE_TOLERANCE
        type_match = TYPE_MAP.get(logged_entry["bug_type"]) == r["claim"]

        if line_close and type_match:
            true_positives += 1
        else:
            mismatches.append({
                "file": base,
                "category": cat,
                "agent_claim": {"line": r["line"], "claim": r["claim"]},
                "ground_truth": {
                    "line": logged_entry["line"],
                    "bug_type": logged_entry["bug_type"],
                    "function": logged_entry["function"],
                },
            })

    # --- Write results ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "audit_details.json"), "w") as f:
        json.dump({
            "grounded_total": grounded_total,
            "true_positives": true_positives,
            "mismatches": mismatches,
            "no_entry_claims": no_entry_claims,
        }, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "empty_files.json"), "w") as f:
        json.dump(empty_files, f, indent=2)

    # --- Print a quick summary to the terminal ---
    print(f"Grounded claims checked: {grounded_total}")
    print(f"True positives (match injection log): {true_positives}")
    print(f"Mismatches: {len(mismatches)}")
    print(f"Claims with no matching injection-log entry: {len(no_entry_claims)}")
    print()
    for cat, files in empty_files.items():
        print(f"{cat}: {len(files)} files with zero comments")


if __name__ == "__main__":
    main()
