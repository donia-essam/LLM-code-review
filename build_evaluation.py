import json
from collections import Counter

with open("scale_up_verification_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

results = data["results"]

print("=" * 80)
print("VERIFIER RESULTS BY DATASET")
print("=" * 80)

stats = {}

for r in results:
    path = r["file_path"]

    if "\\data\\" in path:
        dataset = path.split("\\data\\")[1].split("\\")[0]
    else:
        dataset = "unknown"

    if dataset not in stats:
        stats[dataset] = Counter()

    stats[dataset]["total_claims"] += 1
    stats[dataset][r["status"]] += 1
    stats[dataset][r["claim"]] += 1

for dataset, s in sorted(stats.items()):
    print(f"\n{dataset}")
    print("-" * 40)
    print("Total claims:", s["total_claims"])
    print("Grounded:", s["grounded"])
    print("Hallucinated:", s["hallucinated"])
    print("Off-by-one:", s["off_by_one_bound"])
    print("Null safety:", s["null_safety_violation"])
    print("Unused variable:", s["unused_variable"])