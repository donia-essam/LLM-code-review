import ast
import json
from pathlib import Path

def scan_codebase(repo_path):
    results = []
    repo_path = Path(repo_path)
    
    for py_file in repo_path.rglob("*.py"):
        if "test" in str(py_file).lower():
            continue
        if py_file.name in ["__init__.py", "setup.py", "conf.py"]:
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    lines = content.splitlines()
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 10
                    snippet = "\n".join(lines[start_line:end_line])
                    
                    results.append({
                        "file": str(py_file.relative_to(repo_path)),
                        "function": node.name,
                        "line": node.lineno,
                        "snippet": snippet,
                        "num_lines": end_line - start_line
                    })
        except SyntaxError as e:
            print(f"Skipping {py_file}: SyntaxError - {e}")
        except Exception as e:
            print(f"Skipping {py_file}: {e}")
    
    return results

if __name__ == "__main__":
    
    repo_path = "data/clean/algorithms/algorithms"
    functions = scan_codebase(repo_path)
    
    with open("ground_truth/function_catalog.json", "w") as f:
        json.dump(functions, f, indent=2)
    
    print(f"Found {len(functions)} functions total.")
    print(f"Saved to ground_truth/function_catalog.json")
    
    
    files = {}
    for f in functions:
        files[f["file"]] = files.get(f["file"], 0) + 1
    
    print(f"\nUnique files: {len(files)}")
    print("\nFiles with most functions:")
    for file_path, count in sorted(files.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {file_path}: {count} functions")