from pathlib import Path

from scoring import (
    CommentRecord,
    InjectionRecord,
    load_injection_log,
    load_review_results,
    match_comment_to_bug,
    classify_comments,
    compute_metrics,
    aggregate_metrics,
)


def test_loaders_and_matching():
    repo_root = Path(__file__).resolve().parents[1]
    injections = load_injection_log(repo_root / "code_review_project" / "ground_truth" / "injection_log.json")
    assert injections, "expected at least one injection record"

    review_payload = load_review_results(repo_root / "review_results.json")
    assert review_payload.comments, "expected review comments"

    # The static example in the repo uses a mock comment payload, so the smoke test
    # uses a synthetic matching pair to verify the matcher logic end-to-end.
    synthetic_comment = CommentRecord(file="clone_graph.py", line=3, entity="x", claim="unused_variable")
    synthetic_bug = InjectionRecord(file="data/mutated/algorithms/clone_graph.py", line=3, bug_type="unused_variable", description="Injected unused variable in clone_graph")
    assert match_comment_to_bug(synthetic_comment, synthetic_bug) is not None

    classifications = classify_comments([synthetic_comment], [synthetic_bug])
    assert classifications[0].label == "TP"

    metrics = compute_metrics(classifications, [synthetic_bug])
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0


def test_aggregate_metrics():
    bug = InjectionRecord(file="a.py", line=1, bug_type="unused_variable", description="")
    run_metrics = [
        compute_metrics(classify_comments([CommentRecord(file="a.py", line=1, entity="x", claim="unused_variable")], [bug]), [bug]),
        compute_metrics(classify_comments([CommentRecord(file="a.py", line=2, entity="y", claim="unused_variable")], [bug]), [bug]),
    ]
    aggregated = aggregate_metrics(run_metrics)
    assert aggregated.mean_precision >= 0.0
    assert aggregated.std_precision >= 0.0
