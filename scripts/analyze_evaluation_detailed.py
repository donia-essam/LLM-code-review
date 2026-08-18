import json
import os
import glob
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.loader import load_injection_log
from scoring.matcher import match_comment_to_bug, _normalize_bug_type
from scoring.models import CommentRecord, InjectionRecord
INJECTION_LOG_PATH = ROOT / "code_review_project" / "ground_truth" / "injection_log.json"
REVIEW_INPUTS_DIR = ROOT / "artifacts" / "review_inputs"
PROPOSED_DIR = ROOT / "artifacts" / "proposed_outputs"
BASELINE_B_DIR = ROOT / "artifacts" / "baseline_b_outputs"

bugs = load_injection_log(INJECTION_LOG_PATH)
print(f"Loaded {len(bugs)} injected bugs from log.")

bugs_by_type = defaultdict(list)
for b in bugs:
    norm_type = _normalize_bug_type(b.bug_type)
    bugs_by_type[norm_type].append(b)

print("Bug counts by type:", {k: len(v) for k, v in bugs_by_type.items()})

input_files = sorted(REVIEW_INPUTS_DIR.glob("*.json"))
print(f"Found {len(input_files)} review input files.")

all_comments = []

for inp_path in input_files:
    data = json.loads(inp_path.read_text(encoding="utf-8"))
    prop_path = PROPOSED_DIR / inp_path.name
    bb_path = BASELINE_B_DIR / f"{inp_path.stem}.baseline_b.json"
    if not bb_path.exists():
        bb_path = BASELINE_B_DIR / inp_path.name
    
    prop_data = json.loads(prop_path.read_text(encoding="utf-8")) if prop_path.exists() else {"comments": []}
    bb_data = json.loads(bb_path.read_text(encoding="utf-8")) if bb_path.exists() else {"comments": []}
    
    raw_comments = data.get("comments", [])
    prop_comments = prop_data.get("comments", [])
    bb_comments = bb_data.get("comments", [])
    
    for idx, c in enumerate(raw_comments):
        file_name = c.get("file", "")
        line = int(c.get("line", 0))
        entity = c.get("entity", "")
        claim = c.get("claim", "")
        norm_claim = _normalize_bug_type(claim)
        
        prop_g = prop_comments[idx].get("grounded") if idx < len(prop_comments) else None
        bb_g = bb_comments[idx].get("baseline_b_plausible") if idx < len(bb_comments) else (bb_comments[idx].get("grounded") if idx < len(bb_comments) else None)
        
        crec = CommentRecord(file=file_name, line=line, entity=entity, claim=claim)
        matched_bug = None
        for b in bugs:
            if match_comment_to_bug(crec, b):
                matched_bug = b
                break
        
        is_tp = matched_bug is not None
        all_comments.append({
            "run_file": inp_path.name,
            "comment": crec,
            "claim_type": norm_claim,
            "is_tp": is_tp,
            "matched_bug": matched_bug,
            "proposed_grounded": prop_g,
            "baseline_b_plausible": bb_g
        })

print(f"Total evaluated comments across all runs: {len(all_comments)}")
total_tp = sum(1 for c in all_comments if c["is_tp"])
total_fp = sum(1 for c in all_comments if not c["is_tp"])
print(f"Ground truth breakdown: TP (real bugs) = {total_tp}, FP (hallucinations) = {total_fp}")

# Proposed detector stats
prop_tp_grounded = sum(1 for c in all_comments if c["is_tp"] and c["proposed_grounded"] is True)
prop_fp_grounded = sum(1 for c in all_comments if not c["is_tp"] and c["proposed_grounded"] is True)
prop_tp_ungrounded = sum(1 for c in all_comments if c["is_tp"] and c["proposed_grounded"] is False)
prop_fp_ungrounded = sum(1 for c in all_comments if not c["is_tp"] and c["proposed_grounded"] is False)

print("\n--- PROPOSED VERIFIER DETECTOR METRICS ---")
print(f"TP correctly grounded (TP retention): {prop_tp_grounded}/{total_tp} ({prop_tp_grounded/total_tp*100:.2f}%)")
print(f"FP correctly caught as hallucination: {prop_fp_ungrounded}/{total_fp} ({prop_fp_ungrounded/total_fp*100:.2f}%)")
print(f"FP falsely grounded (hallucination leak): {prop_fp_grounded}/{total_fp} ({prop_fp_grounded/total_fp*100:.2f}%)")

# Baseline B detector stats
bb_tp_grounded = sum(1 for c in all_comments if c["is_tp"] and c["baseline_b_plausible"] is True)
bb_fp_grounded = sum(1 for c in all_comments if not c["is_tp"] and c["baseline_b_plausible"] is True)
bb_tp_ungrounded = sum(1 for c in all_comments if c["is_tp"] and c["baseline_b_plausible"] is False)
bb_fp_ungrounded = sum(1 for c in all_comments if not c["is_tp"] and c["baseline_b_plausible"] is False)

print("\n--- BASELINE B PROXY DETECTOR METRICS ---")
print(f"TP judged plausible: {bb_tp_grounded}/{total_tp} ({bb_tp_grounded/total_tp*100:.2f}%)")
print(f"FP caught as hallucination: {bb_fp_ungrounded}/{total_fp} ({bb_fp_ungrounded/total_fp*100:.2f}%)")
print(f"FP falsely judged plausible: {bb_fp_grounded}/{total_fp} ({bb_fp_grounded/total_fp*100:.2f}%)")

# System-level Post-Filter Metrics
print("\n--- SYSTEM-LEVEL METRICS (3 REPEATS TOTALS) ---")
# Total injected bugs over 3 runs = 180 * 3 = 540 if each file run 3 times, or based on actual run files:
# Let's count total injected bugs in the dataset runs:
# Each file with an injected bug evaluated across runs
total_injected_opportunities = 1212  # from compute_counts / injection runs

print(f"Baseline A (Unfiltered Raw LLM Reviewer):")
print(f"  Emitted Comments: {len(all_comments)} (TP={total_tp}, FP={total_fp})")
print(f"  Precision: {total_tp/(total_tp+total_fp):.4f}")
print(f"  Recall (TP / {total_injected_opportunities}): {total_tp/total_injected_opportunities:.4f}")
print(f"  F1: {2*(total_tp/(total_tp+total_fp))*(total_tp/total_injected_opportunities)/((total_tp/(total_tp+total_fp))+(total_tp/total_injected_opportunities)):.4f}")
print(f"  Hallucination Rate: {total_fp/len(all_comments):.4f}")

prop_passed_all = [c for c in all_comments if c["proposed_grounded"] is True]
prop_p_tp = sum(1 for c in prop_passed_all if c["is_tp"])
prop_p_fp = sum(1 for c in prop_passed_all if not c["is_tp"])
print(f"\nProposed (Grounded Verifier Filtered Reviewer):")
print(f"  Emitted Comments: {len(prop_passed_all)} (TP={prop_p_tp}, FP={prop_p_fp})")
print(f"  Precision: {prop_p_tp/(prop_p_tp+prop_p_fp):.4f}")
print(f"  Recall (TP / {total_injected_opportunities}): {prop_p_tp/total_injected_opportunities:.4f}")
p_prec = prop_p_tp/(prop_p_tp+prop_p_fp)
p_rec = prop_p_tp/total_injected_opportunities
print(f"  F1: {2*p_prec*p_rec/(p_prec+p_rec):.4f}")
print(f"  Hallucination Rate: {prop_p_fp/len(prop_passed_all):.4f}")

# RQ3 breakdown by bug class
print("\n--- RQ3: DETAILED BREAKDOWN BY BUG CLASS ---")
for btype in ["unused_variable", "null_safety", "off_by_one"]:
    type_comments = [c for c in all_comments if c["claim_type"] == btype]
    type_bugs = bugs_by_type[btype]
    t_tp = sum(1 for c in type_comments if c["is_tp"])
    t_fp = sum(1 for c in type_comments if not c["is_tp"])
    
    t_prop_tp_g = sum(1 for c in type_comments if c["is_tp"] and c["proposed_grounded"] is True)
    t_prop_fp_caught = sum(1 for c in type_comments if not c["is_tp"] and c["proposed_grounded"] is False)
    
    t_bb_tp_g = sum(1 for c in type_comments if c["is_tp"] and c["baseline_b_plausible"] is True)
    t_bb_fp_caught = sum(1 for c in type_comments if not c["is_tp"] and c["baseline_b_plausible"] is False)
    
    print(f"\n==========================================")
    print(f"Bug Type: {btype.upper()}")
    print(f"==========================================")
    print(f"  Injected Benchmark Bugs: {len(type_bugs)}")
    print(f"  Candidate Review Comments: {len(type_comments)} (TP={t_tp}, FP={t_fp})")
    print(f"  Raw Reviewer (Baseline A):")
    print(f"    - Precision: {t_tp/(t_tp+t_fp):.4f}")
    print(f"    - Hallucination Rate: {t_fp/(t_tp+t_fp):.4f}")
    print(f"  Proposed Verifier Performance on {btype}:")
    print(f"    - TP Retention (Grounding Accuracy): {t_prop_tp_g}/{t_tp} ({t_prop_tp_g/t_tp*100:.2f}%)")
    print(f"    - Hallucination Catch Rate: {t_prop_fp_caught}/{t_fp} ({t_prop_fp_caught/t_fp*100:.2f}%)")
    prop_passed = [c for c in type_comments if c["proposed_grounded"] is True]
    p_tp = sum(1 for c in prop_passed if c["is_tp"])
    p_fp = sum(1 for c in prop_passed if not c["is_tp"])
    p_prec = p_tp / (p_tp + p_fp) if (p_tp + p_fp) else 0.0
    p_hallu = p_fp / len(prop_passed) if prop_passed else 0.0
    print(f"    - Verified Output Comments: {len(prop_passed)} (TP={p_tp}, FP={p_fp})")
    print(f"    - Verified Precision: {p_prec:.4f}")
    print(f"    - Verified Hallucination Rate: {p_hallu:.4f}")
