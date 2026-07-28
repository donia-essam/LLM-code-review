import ast
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logging_utils import log_injection

def inject_unused_variable(clean_file_path, target_func_name, output_dir="data/mutated"):
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
    insert_idx = target_node.lineno
    
    if target_node.body and isinstance(target_node.body[0], ast.Expr):
        docstring_node = target_node.body[0]
        if isinstance(docstring_node.value, ast.Constant) and isinstance(docstring_node.value.value, str):
            insert_idx = docstring_node.lineno + 1
        else:
            insert_idx = target_node.lineno + 1
    else:
        insert_idx = target_node.lineno + 1
    
    insert_pos = insert_idx - 1
    
    indent = "    "
    if target_node.body:
        first_body_line = target_node.body[0].lineno - 1
        if first_body_line < len(lines) and lines[first_body_line].strip():
            indent = lines[first_body_line][:len(lines[first_body_line]) - len(lines[first_body_line].lstrip())]
    
    mutated_lines = lines[:insert_pos]
    mutated_lines.append(f"{indent}unused_temp = 42  # injected unused variable")
    mutated_lines.extend(lines[insert_pos:])
    mutated_content = "\n".join(mutated_lines)
    
    # Determine output path relative to data/clean/algorithms/algorithms/
    rel_path = clean_file_path.relative_to("data/clean/algorithms/algorithms")
    mutated_path = output_dir / "algorithms" / rel_path
    mutated_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(mutated_path, 'w', encoding='utf-8') as f:
        f.write(mutated_content)
    
    log_injection(
        file_path=str(mutated_path),
        function_name=target_func_name,
        line_num=insert_idx,
        bug_type="unused_variable",
        description=f"Injected unused variable in {target_func_name} at line {insert_idx}",
        original_code=original_content,
        mutated_code=mutated_content
    )
    
    print(f"Injected unused variable in {target_func_name} at line {insert_idx}")
    return mutated_path

if __name__ == "__main__":
    import json
    
    with open("ground_truth/target_functions.json", "r") as f:
        targets = json.load(f)
    
    run_all = len(sys.argv) > 1 and sys.argv[1] == "--all"
    
    if run_all:
        print(f"Injecting unused variables into {len(targets)} functions...")
        print("=" * 50)
        for i, target in enumerate(targets):
            clean_file = Path("data/clean/algorithms/algorithms") / target["file"]
            func_name = target["function"]
            if not clean_file.exists():
                print(f"File not found: {clean_file}")
                continue
            print(f"[{i+1}/{len(targets)}] {func_name} in {target['file']}")
            inject_unused_variable(clean_file, func_name)
        print("\n" + "=" * 50)
        print("Done! Check data/mutated/ and ground_truth/injection_log.jsonl")
    else:
        first = targets[0]
        clean_file = Path("data/clean/algorithms/algorithms") / first["file"]
        print(f"Test mode: injecting into first target only: {first['function']}")
        inject_unused_variable(clean_file, first["function"])
        print("\nRun with --all to process all functions")