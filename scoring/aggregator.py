from __future__ import annotations

from statistics import mean, pstdev
from typing import List

from .models import AggregatedMetrics, MetricsResult


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
