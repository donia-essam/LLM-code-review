import ast
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logging_utils import log_injection

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
                    break
    
    if not found_check:
        if target_node.args.args:
            param_name = target_node.args.args[0].arg
            insert_idx = target_node.lineno + 1
            indent = "    "
            if target_node.body:
                first_body_line = target_node.body[0].lineno - 1
                if first_body_line < len(lines) and lines[first_body_line].strip():
                    indent = lines[first_body_line][:len(lines[first_body_line]) - len(lines[first_body_line].lstrip())]
            
            mutated_lines = lines[:insert_idx]
            mutated_lines.append(f"{indent}{param_name}.strip()  # injected dereference without None check")
            mutated_lines.extend(lines[insert_idx:])
            mutated_content = "\n".join(mutated_lines)
        else:
            insert_idx = target_node.lineno + 1
            indent = "    "
            mutated_lines = lines[:insert_idx]
            mutated_lines.append(f"{indent}temp_var = None  # injected")
            mutated_lines.append(f"{indent}temp_var.strip()  # injected dereference without None check")
            mutated_lines.extend(lines[insert_idx:])
            mutated_content = "\n".join(mutated_lines)
    
    rel_path = clean_file_path.relative_to("data/clean/algorithms/algorithms")
    mutated_path = output_dir / "algorithms" / rel_path
    mutated_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(mutated_path, 'w', encoding='utf-8') as f:
        f.write(mutated_content)
    
    log_injection(
        file_path=str(mutated_path),
        function_name=target_func_name,
        line_num=0,
        bug_type="null_safety",
        description=f"Injected null-safety bug in {target_func_name}",
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