import ast
import sys
import re
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logging_utils import log_injection
from tools.mutation_utils import get_insertion_point


def _try_mutate_range_call(target_node, lines, mutated_lines):
    """
    FIX: original code only looked at `ast.For` nodes whose `.iter` was
    directly a `range(...)` call, missing range() used in comprehensions,
    generator expressions, or nested calls. Walk ALL Call nodes instead.
    """
    for node in ast.walk(target_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range':
            line_num = node.lineno - 1
            if line_num >= len(lines):
                continue
            line_content = lines[line_num]
            if 'range(' not in line_content:
                continue  # multi-line call; skip rather than risk a bad regex edit
            if 'test' in target_node.name.lower() or 'check' in target_node.name.lower():
                new_line = re.sub(r'range\(([^,)]+)\)', r'range(\1 - 1)', line_content, count=1)
            else:
                new_line = re.sub(r'range\(([^,)]+)\)', r'range(\1 + 1)', line_content, count=1)
            if new_line != line_content:
                mutated_lines[line_num] = new_line
                return True, node.lineno
    return False, None


def _try_mutate_loop_comparison(target_node, lines, mutated_lines):
    """
    Flip a bounds comparison against len(...) in a while-loop OR an
    if-guard (FIX: original only checked ast.While, missing off-by-one
    guards written as `if i >= len(x): break` etc.).
    """
    for node in ast.walk(target_node):
        if isinstance(node, (ast.While, ast.If)):
            line_num = node.lineno - 1
            if line_num >= len(lines):
                continue
            line_content = lines[line_num]
            if 'len' not in line_content:
                continue
            if '<=' in line_content:
                new_line = line_content.replace('<=', '<', 1)
            elif '<' in line_content:
                new_line = line_content.replace('<', '<=', 1)
            elif '>=' in line_content:
                new_line = line_content.replace('>=', '>', 1)
            elif '>' in line_content:
                new_line = line_content.replace('>', '>=', 1)
            else:
                continue
            mutated_lines[line_num] = new_line
            return True, node.lineno
    return False, None


def _try_mutate_len_offset(target_node, lines, mutated_lines):
    """
    Flip an existing `len(x) - 1` / `len(x) + 1` offset, a very common
    real-world off-by-one source (e.g. slicing bounds, last-index math).
    """
    pattern = re.compile(r'(len\([^)]*\))\s*([+-])\s*1\b')
    # Scan line-by-line within the function's span rather than per-node,
    # since this pattern can appear inside expressions of many node types
    # (slices, comparisons, arithmetic) and isn't worth special-casing each.
    start_line = target_node.lineno - 1
    end_line = target_node.end_lineno if hasattr(target_node, 'end_lineno') else len(lines)
    for i in range(start_line, min(end_line, len(lines))):
        m = pattern.search(lines[i])
        if m:
            flipped = '+' if m.group(2) == '-' else '-'
            new_line = pattern.sub(rf'\1 {flipped} 1', lines[i], count=1)
            mutated_lines[i] = new_line
            return True, i + 1
    return False, None


def inject_off_by_one(clean_file_path, target_func_name, output_dir="data/mutated_offbyone"):
    clean_file_path = Path(clean_file_path)
    output_dir = Path(output_dir)

    with open(clean_file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    tree = ast.parse(original_content)

    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == target_func_name:
            target_node = node
            break

    if target_node is None:
        print(f"Function '{target_func_name}' not found in {clean_file_path}")
        return None

    lines = original_content.splitlines()
    mutated_lines = lines[:]
    injected_line = None
    synthetic = False

    # Try, in order of realism, to mutate something that's actually there.
    found, injected_line = _try_mutate_range_call(target_node, lines, mutated_lines)
    if not found:
        found, injected_line = _try_mutate_loop_comparison(target_node, lines, mutated_lines)
    if not found:
        found, injected_line = _try_mutate_len_offset(target_node, lines, mutated_lines)

    if not found:
        # No mutable loop-bound pattern exists in this function at all.
        # FIX (previous behavior): inserting a disconnected dummy loop
        # here doesn't represent a real off-by-one bug even once the
        # docstring-insertion bug is fixed, and it silently degraded the
        # dataset (89% of these fallback cases were also landing inside
        # docstrings). We keep a clearly-marked synthetic fallback for
        # completeness, but flag it so target selection can be improved
        # to avoid picking functions with nothing to mutate (see
        # tools/select_files.py TODO).
        insert_idx, indent = get_insertion_point(target_node, lines)
        insert_pos = insert_idx - 1
        mutated_lines = lines[:insert_pos]
        mutated_lines.append(f"{indent}# injected off-by-one loop (should be n-1)")
        mutated_lines.append(f"{indent}for i in range(10):  # should be range(9)")
        mutated_lines.append(f"{indent}    print(i)")
        mutated_lines.extend(lines[insert_pos:])
        injected_line = insert_idx
        synthetic = True
        print(f"  [warn] no real loop-bound pattern found in {target_func_name}; "
              f"used synthetic fallback (flagged in log)")

    mutated_content = "\n".join(mutated_lines)

    rel_path = clean_file_path.relative_to("data/clean/algorithms/algorithms")
    mutated_path = output_dir / "algorithms" / rel_path
    mutated_path.parent.mkdir(parents=True, exist_ok=True)

    with open(mutated_path, 'w', encoding='utf-8') as f:
        f.write(mutated_content)

    log_injection(
        file_path=str(mutated_path),
        function_name=target_func_name,
        # FIX: was hardcoded to 0.
        line_num=injected_line,
        bug_type="off_by_one",
        description=(
            f"Injected off-by-one bug in {target_func_name} at line {injected_line}"
            + (" [SYNTHETIC: no real loop bound found]" if synthetic else "")
        ),
        original_code=original_content,
        mutated_code=mutated_content
    )

    print(f"Injected off-by-one bug in {target_func_name}")
    return mutated_path


if __name__ == "__main__":
    import json

    # FIX: off-by-one uses its own target list (functions confirmed to
    # contain a mutable loop-bound pattern -- see tools/select_files.py),
    # instead of reusing the generic target_functions.json, so it doesn't
    # fall back to a synthetic/disconnected stub for most of the dataset.
    target_path = Path("ground_truth/target_functions_offbyone.json")
    if not target_path.exists():
        print(f"{target_path} not found -- run `python tools/select_files.py` first.")
        sys.exit(1)
    with open(target_path, "r") as f:
        targets = json.load(f)

    run_all = len(sys.argv) > 1 and sys.argv[1] == "--all"

    if run_all:
        print(f"Injecting off-by-one bugs into {len(targets)} functions...")
        print("=" * 50)
        for i, target in enumerate(targets):
            clean_file = Path("data/clean/algorithms/algorithms") / target["file"]
            func_name = target["function"]
            if not clean_file.exists():
                print(f"File not found: {clean_file}")
                continue
            print(f"[{i+1}/{len(targets)}] {func_name} in {target['file']}")
            inject_off_by_one(clean_file, func_name)
        print("\n" + "=" * 50)
        print("Done! Check data/mutated_offbyone/ and ground_truth/injection_log.jsonl")
    else:
        first = targets[0]
        clean_file = Path("data/clean/algorithms/algorithms") / first["file"]
        print(f"Test mode: injecting into first target only: {first['function']}")
        inject_off_by_one(clean_file, first["function"])
        print("\nRun with --all to process all functions")
