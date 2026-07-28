import ast
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logging_utils import log_injection
from tools.mutation_utils import get_insertion_point


def _annotation_mentions_none(annotation) -> bool:
    """True if a param's type annotation is Optional[...] or `X | None`."""
    if annotation is None:
        return False
    dumped = ast.dump(annotation)
    if "Optional" in dumped:
        return True
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        for side in (annotation.left, annotation.right):
            if isinstance(side, ast.Constant) and side.value is None:
                return True
            if isinstance(side, ast.Name) and side.id == "None":
                return True
    return False


def _find_nullable_param(target_node):
    """
    Find a parameter that's plausibly nullable: either annotated
    Optional[...]/`X | None`, or compared to `None` somewhere in the
    function body (e.g. `if x is not None:`). Returns the param name,
    or None if nothing plausible is found.
    """
    for arg in target_node.args.args:
        if _annotation_mentions_none(arg.annotation):
            return arg.arg

    param_names = {a.arg for a in target_node.args.args}
    for node in ast.walk(target_node):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            if node.left.id in param_names:
                for op, comparator in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
                        if isinstance(comparator, ast.Constant) and comparator.value is None:
                            return node.left.id
    return None


def inject_null_safety_bug(clean_file_path, target_func_name, output_dir="data/mutated_null"):
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
    found_check = False
    injected_line = None

    # Case 1: an existing `if x is not None:` guard exists -- remove the
    # guard but keep its body, so the dereference becomes unguarded.
    for node in ast.walk(target_node):
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Compare):
                if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.IsNot):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else len(lines)

                    body_lines = []
                    for i in range(start_line + 1, end_line):
                        if i < len(lines):
                            line = lines[i]
                            if line.strip():
                                if line.startswith("    "):
                                    body_lines.append(line[4:])
                                else:
                                    body_lines.append(line)

                    mutated_lines = lines[:start_line] + body_lines + lines[end_line:]
                    mutated_content = "\n".join(mutated_lines)
                    found_check = True
                    # FIX: was `node.lineno` (the removed `if` line's
                    # original number). Removing that one line shifts
                    # everything below it up by one, so the now-unguarded
                    # body actually starts at its old position minus 1.
                    injected_line = node.body[0].lineno - 1
                    break

    # Case 2: no existing guard to strip -- inject an unguarded dereference
    # on a parameter that's plausibly nullable (Optional-annotated, or
    # already compared to None elsewhere in the function). This avoids the
    # old bug of calling `.strip()` on an arbitrary, possibly non-string
    # parameter regardless of type.
    if not found_check:
        insert_idx, indent = get_insertion_point(target_node, lines)
        insert_pos = insert_idx - 1

        nullable_param = _find_nullable_param(target_node)
        mutated_lines = lines[:insert_pos]
        if nullable_param:
            mutated_lines.append(
                f"{indent}{nullable_param}.strip()  # injected dereference without None check"
            )
            # Single inserted line -- the dereference IS this line.
            injected_line = insert_idx
        else:
            # No plausibly-nullable param found in this function -- use a
            # synthetic (but always type-valid) dereference instead of
            # guessing at an existing parameter's type.
            mutated_lines.append(f"{indent}temp_var = None  # injected")
            mutated_lines.append(
                f"{indent}temp_var.strip()  # injected dereference without None check"
            )
            # FIX: two lines inserted here -- the actual dereference is the
            # SECOND one, not insert_idx (which pointed at "temp_var = None").
            injected_line = insert_idx + 1
        mutated_lines.extend(lines[insert_pos:])
        mutated_content = "\n".join(mutated_lines)

    rel_path = clean_file_path.relative_to("data/clean/algorithms/algorithms")
    mutated_path = output_dir / "algorithms" / rel_path
    mutated_path.parent.mkdir(parents=True, exist_ok=True)

    with open(mutated_path, 'w', encoding='utf-8') as f:
        f.write(mutated_content)

    mechanism = "guard-removed" if found_check else "synthetic-dereference"
    log_injection(
        file_path=str(mutated_path),
        function_name=target_func_name,
        # FIX: was hardcoded to 0 -- now records the actual injection line,
        # which the verifier needs to check entity/location grounding.
        line_num=injected_line,
        bug_type="null_safety",
        description=(
            f"Injected null-safety bug in {target_func_name} at line "
            f"{injected_line} [{mechanism}]"
        ),
        original_code=original_content,
        mutated_code=mutated_content
    )

    print(f"Injected null-safety bug in {target_func_name}")
    return mutated_path


if __name__ == "__main__":
    import json

    with open("ground_truth/target_functions.json", "r") as f:
        targets = json.load(f)

    run_all = len(sys.argv) > 1 and sys.argv[1] == "--all"

    if run_all:
        print(f"Injecting null-safety bugs into {len(targets)} functions...")
        print("=" * 50)
        for i, target in enumerate(targets):
            clean_file = Path("data/clean/algorithms/algorithms") / target["file"]
            func_name = target["function"]
            if not clean_file.exists():
                print(f"File not found: {clean_file}")
                continue
            print(f"[{i+1}/{len(targets)}] {func_name} in {target['file']}")
            inject_null_safety_bug(clean_file, func_name)
        print("\n" + "=" * 50)
        print("Done! Check data/mutated_null/ and ground_truth/injection_log.jsonl")
    else:
        first = targets[0]
        clean_file = Path("data/clean/algorithms/algorithms") / first["file"]
        print(f"Test mode: injecting into first target only: {first['function']}")
        inject_null_safety_bug(clean_file, first["function"])
        print("\nRun with --all to process all functions")
