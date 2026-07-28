import json

with open("ground_truth/function_catalog.json", "r") as f:
    all_funcs = json.load(f)

# Get all unique files
all_files = sorted(set(f["file"] for f in all_funcs))
print(f"Total files available: {len(all_files)}")

# Select 60 
selected_files = all_files[:60]
print(f"Selected {len(selected_files)} files for mutation")


targets = []
for file_path in selected_files:
    
    for f in all_funcs:
        if f["file"] == file_path:
            targets.append({
                "file": file_path,  
                "function": f["function"],
                "line": f["line"],
                "num_lines": f["num_lines"]
            })
            break

# Save targets
with open("ground_truth/target_functions.json", "w") as f:
    json.dump(targets, f, indent=2)

print(f"Created {len(targets)} file-level targets")
print("\nFirst 10 targets:")
for t in targets[:10]:
    print(f"  {t['file']} -> {t['function']} ({t['num_lines']} lines)")