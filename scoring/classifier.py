from __future__ import annotations

from typing import List, Optional

from .matcher import match_comment_to_bug, LINE_TOLERANCE
from .models import ClassificationResult, CommentRecord, InjectionRecord


def classify_comments(
    comments: List[CommentRecord],
    bugs: List[InjectionRecord],
    line_tolerance: int = LINE_TOLERANCE,
    verifier_enabled: bool = False,
) -> List[ClassificationResult]:
    """Classify each comment as TP, hallucination, or grounded_but_wrong."""

    results: List[ClassificationResult] = []
    for comment in comments:
        matched_bug: Optional[InjectionRecord] = None
        if bugs:
            for bug in bugs:
                if match_comment_to_bug(comment, bug, line_tolerance=line_tolerance):
                    matched_bug = bug
                    break

        if matched_bug is not None:
            label = "TP"
            grounded = comment.grounded
        else:
            if verifier_enabled and comment.grounded is True:
                label = "grounded_but_wrong"
            else:
                label = "hallucination"
            grounded = comment.grounded

        results.append(
            ClassificationResult(
                comment=comment,
                matched_bug=matched_bug,
                label=label,
                grounded=grounded,
            )
        )
    return results
