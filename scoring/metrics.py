from __future__ import annotations

from statistics import mean, pstdev
from typing import List, Optional

from .classifier import classify_comments
from .models import AggregatedMetrics, ClassificationResult, InjectionRecord, MetricsResult
from .matcher import LINE_TOLERANCE


def compute_metrics(
    classifications: List[ClassificationResult],
    bugs: List[InjectionRecord],
    verifier_enabled: bool = False,
) -> MetricsResult:
    """Compute precision, recall, F1, hallucination rate, and grounding accuracy for one run."""

    tp = sum(1 for item in classifications if item.label == "TP")
    fp = sum(1 for item in classifications if item.label in {"hallucination", "grounded_but_wrong"})
    total_comments = len(classifications)

    matched_bugs = {item.matched_bug for item in classifications if item.matched_bug is not None}
    missed_bugs = [bug for bug in bugs if bug not in matched_bugs]
    fn = len(missed_bugs)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    hallucination_rate = fp / total_comments if total_comments else 0.0

    grounded_tp = [item for item in classifications if item.label == "TP" and item.grounded is True]
    grounding_accuracy = len(grounded_tp) / tp if (tp and verifier_enabled) else None

    return MetricsResult(
        tp=tp,
        fp=fp,
        fn=fn,
        total_comments=total_comments,
        precision=precision,
        recall=recall,
        f1=f1,
        hallucination_rate=hallucination_rate,
        grounding_accuracy=grounding_accuracy,
    )


def aggregate_metrics(run_metrics: List[MetricsResult]) -> AggregatedMetrics:
    """Aggregate multiple runs by mean and standard deviation."""

    if not run_metrics:
        return AggregatedMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None, None)

    precisions = [item.precision for item in run_metrics]
    recalls = [item.recall for item in run_metrics]
    f1_scores = [item.f1 for item in run_metrics]
    hallucination_rates = [item.hallucination_rate for item in run_metrics]
    grounding_values = [item.grounding_accuracy for item in run_metrics if item.grounding_accuracy is not None]

    return AggregatedMetrics(
        mean_precision=mean(precisions),
        std_precision=pstdev(precisions) if len(precisions) > 1 else 0.0,
        mean_recall=mean(recalls),
        std_recall=pstdev(recalls) if len(recalls) > 1 else 0.0,
        mean_f1=mean(f1_scores),
        std_f1=pstdev(f1_scores) if len(f1_scores) > 1 else 0.0,
        mean_hallucination_rate=mean(hallucination_rates),
        std_hallucination_rate=pstdev(hallucination_rates) if len(hallucination_rates) > 1 else 0.0,
        mean_grounding_accuracy=mean(grounding_values) if grounding_values else None,
        std_grounding_accuracy=pstdev(grounding_values) if len(grounding_values) > 1 else 0.0 if grounding_values else None,
    )
