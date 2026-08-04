from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_b_judge import BaselineBJudgment, judge_comment, process_comment_file


def test_judge_comment_returns_structured_payload() -> None:
    comment = {"file": "toy.py", "line": 2, "entity": "x", "claim": "unused_variable"}
    source = "def sample():\n    x = 1\n    return 2\n"

    decision = judge_comment(comment, source, source_path="toy.py")

    assert isinstance(decision, BaselineBJudgment)
    assert isinstance(decision.plausible, bool)
    assert 0.0 <= decision.confidence <= 1.0
    assert isinstance(decision.reasoning, str)


def test_process_comment_file_writes_compatible_json(tmp_path: Path) -> None:
    source_path = tmp_path / "toy.py"
    source_path.write_text("def sample():\n    x = 1\n    return 2\n", encoding="utf-8")

    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "comments": [
                    {
                        "file": "toy.py",
                        "line": 2,
                        "entity": "x",
                        "claim": "unused_variable",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = process_comment_file(review_path, source_root=tmp_path, output_path=tmp_path / "out.json")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "comments" in payload
    assert payload["comments"][0]["file"] == "toy.py"
    assert "grounded" in payload["comments"][0]
    assert "baseline_b_plausible" in payload["comments"][0]
