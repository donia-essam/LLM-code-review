import json

with open("scale_up_verification_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]

cases = [
    r
    for r in results
    if r["static_check"] is True
    and r["ast_line_match"] is False
]

print("Potential localization issues:", len(cases))

for r in cases:
    print(
        f"{r['claim']} | "
        f"{r['file_path']}:{r['line']} | "
        f"entity={r['entity']} | "
        f"status={r['status']}"
    )