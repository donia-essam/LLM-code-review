import json
from collections import defaultdict

with open("scale_up_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

stats = defaultdict(lambda: {
    "total": 0,
    "with_claim": 0,
    "no_claim": 0,
})

for run in data:
    file_path = run["file_path"]
    dataset = file_path.split("\\data\\")[1].split("\\")[0]

    stats[dataset]["total"] += 1

    comments = run.get("output", {}).get("comments", [])

    if comments:
        stats[dataset]["with_claim"] += 1
    else:
        stats[dataset]["no_claim"] += 1

print("=" * 70)
print("LLM DETECTION BY DATASET")
print("=" * 70)

for dataset, s in stats.items():
    print(
        f"{dataset}: "
        f"total={s['total']}, "
        f"with_claim={s['with_claim']}, "
        f"no_claim={s['no_claim']}"
    )