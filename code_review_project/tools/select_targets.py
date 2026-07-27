import json

# Load all functions from the catalog
with open("ground_truth/function_catalog.json", "r") as f:
    all_funcs = json.load(f)

print(f"Total functions found: {len(all_funcs)}")

# Filter: functions between 5-30 lines, not in test files, no dunder methods
targets = []
for f in all_funcs:
    if 5 <= f["num_lines"] <= 30:
        if "test" not in f["file"].lower():
            if not f['function'].startswith('__') and not f['function'].endswith('__'):
                targets.append(f)

print(f"After filtering: {len(targets)} functions match criteria")

# Take first 60
selected = targets[:60]

# Add boltons/ prefix to all file paths
for t in selected:
    if not t['file'].startswith('boltons/'):
        t['file'] = 'boltons/' + t['file']

# Save to file
with open("ground_truth/target_functions.json", "w") as f:
    json.dump(selected, f, indent=2)

print(f"Selected {len(selected)} target functions (excluding dunder methods)")
print("\nFirst 5 targets:")
for t in selected[:5]:
    print(f"  {t['file']} -> {t['function']} ({t['num_lines']} lines)")