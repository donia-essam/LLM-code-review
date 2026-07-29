from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ReviewPayload:
    """Payload returned by the review-results loader."""

    comments: list["CommentRecord"]


@dataclass(slots=True, frozen=True)
class InjectionRecord:
    """Represents one injected bug from the mutator and ground-truth log."""

    file: str
    function: str = ""
    line: int = 0
    bug_type: str = ""
    description: str = ""


@dataclass(slots=True)
class CommentRecord:
    """Represents one structured comment emitted by the review agent."""

    file: str
    line: int
    entity: str
    claim: str
    grounded: Optional[bool] = None


@dataclass(slots=True)
class ClassificationResult:
    """Classification of one comment produced by a system."""

    comment: CommentRecord
    matched_bug: Optional[InjectionRecord]
    label: str
    grounded: Optional[bool]


@dataclass(slots=True)
class MetricsResult:
    """Metrics for one run of one system."""

    tp: int
    fp: int
    fn: int
    total_comments: int
    precision: float
    recall: float
    f1: float
    hallucination_rate: float
    grounding_accuracy: Optional[float]


@dataclass(slots=True)
class AggregatedMetrics:
    """Mean and standard deviation over multiple runs of the same system."""

    mean_precision: float
    std_precision: float
    mean_recall: float
    std_recall: float
    mean_f1: float
    std_f1: float
    mean_hallucination_rate: float
    std_hallucination_rate: float
    mean_grounding_accuracy: Optional[float]
    std_grounding_accuracy: Optional[float]
