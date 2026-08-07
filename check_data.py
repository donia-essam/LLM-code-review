import os
import glob

base_dir = os.path.join("code_review_project", "data")

if os.path.exists(base_dir):
    print("\n--- Data Breakdown ---")
    for group in os.listdir(base_dir):
        group_path = os.path.join(base_dir, group)
        if os.path.isdir(group_path):
            files = glob.glob(os.path.join(group_path, "**", "*.py"), recursive=True)
            print(f" Group: {group} --> {len(files)} files")
    print("----------------------\n")
else:
    print(" Path not found! Check your folder structure.")