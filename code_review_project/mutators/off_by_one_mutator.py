import ast
import sys
import re
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from tools.logging_utils import log_injection

def inject_off_by_one(clean_file_path, target_func_name, output_dir="data/mutated_offbyone"):
    
    clean_file_path = Path(clean_file_path)
    output_dir = Path(output_dir)
    
    with open(clean_file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    tree = ast.parse(original_content)
    
    # Find the target function
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
    found_loop = False
    
    # Look for for loops with range()
    for node in ast.walk(target_node):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'range':
        
                line_num = node.lineno - 1
                line_content = lines[line_num]
                
                if 'test' in target_func_name.lower() or 'check' in target_func_name.lower():
                    mutated_lines[line_num] = re.sub(r'range\(([^,)]+)\)', r'range(\1 - 1)', line_content)
                else:
                    mutated_lines[line_num] = re.sub(r'range\(([^,)]+)\)', r'range(\1 + 1)', line_content)
                found_loop = True
                break
        elif isinstance(node, ast.While):
            
            line_num = node.lineno - 1
            line_content = lines[line_num]
            if '<' in line_content and 'len' in line_content:
        
                mutated_lines[line_num] = line_content.replace('<', '<=')
                found_loop = True
                break
            elif '>' in line_content and 'len' in line_content:
    
                mutated_lines[line_num] = line_content.replace('>', '>=')
                found_loop = True
                break
    
    if not found_loop:
        
        insert_idx = target_node.lineno + 1
        indent = "    "
        if target_node.body:
            first_body_line = target_node.body[0].lineno - 1
            if first_body_line < len(lines) and lines[first_body_line].strip():
                indent = lines[first_body_line][:len(lines[first_body_line]) - len(lines[first_body_line].lstrip())]
        
        mutated_lines = lines[:insert_idx]
        mutated_lines.append(f"{indent}# injected off-by-one loop (should be n-1)")
        mutated_lines.append(f"{indent}for i in range(10):  # should be range(9)")
        mutated_lines.append(f"{indent}    print(i)")
        mutated_lines.extend(lines[insert_idx:])
    
    mutated_content = "\n".join(mutated_lines)
    
    # Determine output path
    rel_path = clean_file_path.relative_to("data/clean")
    mutated_path = output_dir / rel_path
    mutated_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(mutated_path, 'w', encoding='utf-8') as f:
        f.write(mutated_content)
    
    log_injection(
        file_path=str(mutated_path),
        function_name=target_func_name,
        line_num=0,
        bug_type="off_by_one",
        description=f"Injected off-by-one bug in {target_func_name}",
        original_code=original_content,
        mutated_code=mutated_content
    )
    
    print(f"Injected off-by-one bug in {target_func_name}")
    return mutated_path

if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Run on all target functions
        with open("ground_truth/target_functions.json", "r") as f:
            targets = json.load(f)
        print(f"Injecting off-by-one bugs into {len(targets)} functions...")
        print("=" * 50)
        for i, target in enumerate(targets):
            clean_file = Path("data/clean") / target["file"]
            func_name = target["function"]
            if not clean_file.exists():
                print(f"File not found: {clean_file}")
                continue
            print(f"[{i+1}/{len(targets)}] {func_name} in {target['file']}")
            inject_off_by_one(clean_file, func_name, output_dir="data/mutated_offbyone")
        print("\n" + "=" * 50)
        print("Done! Off-by-one mutations saved to data/mutated_offbyone/")
    else:
        # Default: test on first target
        with open("ground_truth/target_functions.json", "r") as f:
            targets = json.load(f)
        first = targets[0]
        clean_file = Path("data/clean") / first["file"]
        inject_off_by_one(clean_file, first["function"])