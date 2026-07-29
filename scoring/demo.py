from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scoring import (
    aggregate_metrics,
    classify_comments,
    compute_metrics,
    load_injection_log,
    load_review_results,
    match_comment_to_bug,
)


def run_demo() -> None:
    """Runs a small demo over the repository's existing sample review output and mutator log."""

    repo_root = Path(__file__).resolve().parents[1]
    injections = load_injection_log(repo_root / "code_review_project" / "ground_truth" / "injection_log.json")
    review_payload = load_review_results(repo_root / "review_results.json")

    if not review_payload.comments:
        raise RuntimeError("review_results.json does not contain any comments")

    synthetic_comment = review_payload.comments[0]
    synthetic_bug = injections[0] if injections else None
    if synthetic_bug is None:
        raise RuntimeError("injection_log.json does not contain any injected bugs")

    matched = match_comment_to_bug(synthetic_comment, synthetic_bug)
    print(f"First match: {matched is not None}")

    classifications = classify_comments(review_payload.comments, injections)
    metrics = compute_metrics(classifications, injections)
    print(f"Precision: {metrics.precision:.3f}")
    print(f"Recall: {metrics.recall:.3f}")
    print(f"F1: {metrics.f1:.3f}")
    print(f"Hallucination rate: {metrics.hallucination_rate:.3f}")
    print(f"Grounding accuracy: {metrics.grounding_accuracy}")

    aggregated = aggregate_metrics([metrics])
    print(f"Aggregated mean precision: {aggregated.mean_precision:.3f}")


if __name__ == "__main__":
    run_demo()
