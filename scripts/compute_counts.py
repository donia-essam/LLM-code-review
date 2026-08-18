import json
import os
import glob

ROOT = os.path.dirname(os.path.dirname(__file__))
EVAL_SUM = os.path.join(ROOT, 'artifacts', 'evaluation_summary.json')
PROPOSED_DIR = os.path.join(ROOT, 'artifacts', 'proposed_outputs')

with open(EVAL_SUM, 'r', encoding='utf-8') as f:
    data = json.load(f)

def sum_run_metrics(section):
    runs = data.get(section, {}).get('run_metrics', [])
    tp = sum(r.get('tp', 0) for r in runs)
    fp = sum(r.get('fp', 0) for r in runs)
    fn = sum(r.get('fn', 0) for r in runs)
    return tp, fp, fn

bb_tp, bb_fp, bb_fn = sum_run_metrics('Baseline B')
prop_tp, prop_fp, prop_fn = sum_run_metrics('Proposed')

# Count grounded values across proposed_outputs files
grounded_true = 0
grounded_false = 0
grounded_null = 0
files = glob.glob(os.path.join(PROPOSED_DIR, '*.json'))
for path in files:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            j = json.load(f)
    except Exception:
        continue
    comments = j.get('comments') or []
    for c in comments:
        g = c.get('grounded')
        if g is True:
            grounded_true += 1
        elif g is False:
            grounded_false += 1
        else:
            grounded_null += 1

print('Baseline B totals:')
print(f'  TP={bb_tp}  FP={bb_fp}  FN={bb_fn}  Denominator(TP+FN)={bb_tp+bb_fn}')
if (bb_tp+bb_fn)>0:
    print(f'  micro_recall={bb_tp/(bb_tp+bb_fn):.6f}')
else:
    print('  micro_recall=nan')

print('\nProposed totals:')
print(f'  TP={prop_tp}  FP={prop_fp}  FN={prop_fn}  Denominator(TP+FN)={prop_tp+prop_fn}')
if (prop_tp+prop_fn)>0:
    print(f'  micro_recall={prop_tp/(prop_tp+prop_fn):.6f}')
else:
    print('  micro_recall=nan')

print('\nProposed grounded counts across artifacts/proposed_outputs:')
print(f'  grounded=True: {grounded_true}')
print(f'  grounded=False: {grounded_false}')
print(f'  grounded=None/missing: {grounded_null}')
print(f'  files_processed: {len(files)}')
