from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scoring.models import CommentRecord, InjectionRecord
from week4_evaluation import score_comment_groups


def test_score_comment_groups_uses_one_metric_per_output_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "baseline_b_outputs"
    output_dir.mkdir()

    first_payload = {
        "comments": [
            {
                "file": "sample.py",
                "line": 1,
                "entity": "value",
                "claim": "unused_variable",
                "baseline_b_plausible": True,
            }
        ]
    }
    second_payload = {
        "comments": [
            {
                "file": "other.py",
                "line": 2,
                "entity": "value",
                "claim": "unused_variable",
                "baseline_b_plausible": False,
            }
        ]
    }

    (output_dir / "first.json").write_text(json.dumps(first_payload), encoding="utf-8")
    (output_dir / "second.json").write_text(json.dumps(second_payload), encoding="utf-8")

    bugs = [InjectionRecord(file="sample.py", line=1, function="demo", bug_type="unused_variable", description="")]
    grouped_comments = [
        [
            CommentRecord(
                file="sample.py",
                line=1,
                entity="value",
                claim="unused_variable",
                grounded=True,
            )
        ],
        [
            CommentRecord(
                file="other.py",
                line=2,
                entity="value",
                claim="unused_variable",
                grounded=False,
            )
        ],
    ]
    run_metrics = score_comment_groups(grouped_comments, bugs)

    assert len(run_metrics) == 2
    assert run_metrics[0].tp == 1
    assert run_metrics[0].fp == 0
    assert run_metrics[1].tp == 0
    assert run_metrics[1].fp == 1
