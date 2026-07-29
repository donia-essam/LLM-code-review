from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import CommentRecord, InjectionRecord

LINE_TOLERANCE = 2


def _normalize_path(value: str) -> str:
    """Normalize file paths so comments and injection logs can be matched across different prefixes."""

    return Path(value).name.lower()


def _normalize_bug_type(value: str) -> str:
    """Normalize review-agent claim names to the mutator log's bug_type names."""

    aliases = {
        "unused_variable": "unused_variable",
        "null_safety_violation": "null_safety",
        "off_by_one_bound": "off_by_one",
        "null_safety": "null_safety",
        "off_by_one": "off_by_one",
    }
    return aliases.get(value, value)


def match_comment_to_bug(comment: CommentRecord, bug: InjectionRecord, line_tolerance: int = LINE_TOLERANCE) -> Optional[InjectionRecord]:
    """Match a comment to an injected bug using file, bug type, line tolerance, and entity overlap."""

    if _normalize_path(comment.file) != _normalize_path(bug.file):
        return None

    if _normalize_bug_type(comment.claim) != _normalize_bug_type(bug.bug_type):
        return None

    if abs(comment.line - bug.line) <= line_tolerance:
        return bug

    entity_text = comment.entity.lower()
    description_text = bug.description.lower()
    if entity_text and entity_text in description_text:
        return bug

    return None
