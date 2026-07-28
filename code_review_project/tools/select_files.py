"""
Select target functions to mutate, one list per bug class.

FIX vs. the original script: the original picked one arbitrary 60-file
slice (first 60 alphabetically) and reused it for all three bug classes.
That's fine for unused-variable and null-safety (any function works --
the mutator can always insert an unused var, and null-safety has a
type-valid synthetic fallback), but off-by-one specifically needs a
function that actually contains a mutable loop bound (a range() call, a
len()-based comparison, or a len(x)+-1 offset) -- and only ~25% of an
arbitrary slice has that. Reusing the same slice for off-by-one meant
75%+ of "off-by-one" mutations were a disconnected synthetic stub rather
than a real bug.

This script instead: (1) selects a general 60-file slice for
unused_variable and null_safety, and (2) filters the FULL catalog down
to functions with a real mutable loop-bound pattern before selecting 60
for off_by_one, so the off-by-one dataset is made of real mutations by
construction rather than by luck.
"""
import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path("data/clean/algorithms/algorithms")


def has_mutable_loop_pattern(func_name: str, file_rel: str) -> bool:
    """True if the function contains something an off-by-one mutation can
    realistically target: a range() call, a len()-based bound comparison
    in a while/if, or an existing len(x) +/- 1 offset."""
    path = REPO_ROOT / file_rel
    if not path.exists():
        return False
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return False

    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            target = node
            break
    if target is None:
        return False

    for node in ast.walk(target):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            return True
        if isinstance(node, (ast.While, ast.If)):
            segment = ast.get_source_segment(src, node) or ""
            first_line = segment.splitlines()[0] if segment else ""
            if "len" in first_line and any(op in first_line for op in ("<=", "<", ">=", ">")):
                return True

    func_src = ast.get_source_segment(src, target) or ""
    if re.search(r"len\([^)]*\)\s*[+-]\s*1\b", func_src):
        return True

    return False


def main():
    with open("ground_truth/function_catalog.json", "r") as f:
        all_funcs = json.load(f)

    # --- General target list (unused_variable, null_safety) ---
    all_files = sorted(set(f["file"] for f in all_funcs))
    print(f"Total files available: {len(all_files)}")
    selected_files = all_files[:60]

    general_targets = []
    for file_path in selected_files:
        for f in all_funcs:
            if f["file"] == file_path:
                general_targets.append({
                    "file": f["file"],
                    "function": f["function"],
                    "line": f["line"],
                    "num_lines": f["num_lines"],
                })
                break

    with open("ground_truth/target_functions.json", "w") as f:
        json.dump(general_targets, f, indent=2)
    print(f"Created {len(general_targets)} general targets -> ground_truth/target_functions.json")

    # --- Off-by-one target list: filtered to functions with a real mutable pattern ---
    eligible = [
        f for f in all_funcs
        if has_mutable_loop_pattern(f["function"], f["file"])
    ]
    print(f"{len(eligible)} / {len(all_funcs)} functions have a mutable loop-bound pattern")

    # one function per file, dedup, then take first 60
    seen_files = set()
    offbyone_targets = []
    for f in eligible:
        if f["file"] in seen_files:
            continue
        seen_files.add(f["file"])
        offbyone_targets.append({
            "file": f["file"],
            "function": f["function"],
            "line": f["line"],
            "num_lines": f["num_lines"],
        })
        if len(offbyone_targets) >= 60:
            break

    with open("ground_truth/target_functions_offbyone.json", "w") as f:
        json.dump(offbyone_targets, f, indent=2)
    print(f"Created {len(offbyone_targets)} off-by-one-eligible targets "
          f"-> ground_truth/target_functions_offbyone.json")

    if len(offbyone_targets) < 40:
        print(f"WARNING: only found {len(offbyone_targets)} eligible functions, "
              f"below the brief's 40-file minimum for this bug class.")


if __name__ == "__main__":
    main()
