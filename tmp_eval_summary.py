import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.').resolve()))
from week4_evaluation import load_comment_groups_from_outputs, score_comment_groups, summarize_metrics
from scoring.loader import load_injection_log

repo = Path('.')
bugs = load_injection_log(repo / 'code_review_project' / 'ground_truth' / 'injection_log.json')
output_dir = repo / 'artifacts' / 'baseline_b_outputs'
comment_groups = load_comment_groups_from_outputs(output_dir)
run_metrics = score_comment_groups(comment_groups, bugs)
summary = summarize_metrics(run_metrics)
print(json.dumps({'summary': summary, 'run_count': len(run_metrics)}, indent=2))
