from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import CommentRecord, InjectionRecord, ReviewPayload


def load_injection_log(path: str | Path) -> List[InjectionRecord]:
    """Load injected bugs from the mutator log JSON array."""

    payload_path = Path(path)
    with payload_path.open("r", encoding="utf-8") as handle:
        entries = json.load(handle)

    return [
        InjectionRecord(
            file=entry["file"],
            function=entry.get("function", ""),
            line=int(entry["line"]),
            bug_type=entry["bug_type"],
            description=entry.get("description", ""),
        )
        for entry in entries
    ]


def load_review_results(path: str | Path) -> ReviewPayload:
    """Load a review-agent JSON payload containing a comments list."""

    payload_path = Path(path)
    with payload_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    comments = [
        CommentRecord(
            file=item["file"],
            line=int(item["line"]),
            entity=item["entity"],
            claim=item["claim"],
            grounded=item.get("grounded"),
        )
        for item in payload.get("comments", [])
    ]

    return ReviewPayload(comments=comments)
