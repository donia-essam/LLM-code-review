from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baseline_b_judge import process_directory
from scoring.classifier import classify_comments
from scoring.loader import load_injection_log
from scoring.metrics import compute_metrics
from scoring.models import CommentRecord, InjectionRecord
from scoring.stats import exact_mcnemar_test
from verifier.verifier import verify_comment


def sanitize_name(value: str) -> str:
    """Create a filesystem-safe stem from a path-like string."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "record"


def load_scale_up_artifact(path: Path) -> List[Dict[str, Any]]:
    """Load a scale-up artifact if it is a list of per-run result records."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return payload["results"]
    raise ValueError(f"Unsupported scale-up artifact structure in {path}")


def write_review_inputs_from_artifact(artifact: List[Dict[str, Any]], output_dir: Path) -> List[Path]:
    """Convert per-run scale-up records into Baseline A-style review JSON files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []
    for index, entry in enumerate(artifact, start=1):
        comments = entry.get("output", {}).get("comments", [])
        if not isinstance(comments, list) or not comments:
            continue
        review_payload = {"comments": comments}
        stem = sanitize_name(str(entry.get("file_path", f"record_{index}")))
        run_id = entry.get("run_id", index)
        output_path = output_dir / f"{stem}_run{run_id}.json"
        output_path.write_text(json.dumps(review_payload, indent=2), encoding="utf-8")
        written_files.append(output_path)
    return written_files


def build_baseline_b_outputs(review_input_dir: Path, output_dir: Path, source_root: Path) -> List[Path]:
    """Run Baseline B over all generated review JSON files and save one result file per input."""

    output_dir.mkdir(parents=True, exist_ok=True)
    return process_directory(review_input_dir, source_root=source_root, output_dir=output_dir)


def load_comment_groups_from_outputs(output_dir: Path) -> List[List[CommentRecord]]:
    """Load verdicts from each per-file JSON output into a separate comment group."""

    comment_groups: List[List[CommentRecord]] = []
    for output_path in sorted(output_dir.glob("*.json")):
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        group: List[CommentRecord] = []
        for item in payload.get("comments", []):
            group.append(
                CommentRecord(
                    file=item.get("file", ""),
                    line=int(item.get("line", 0)),
                    entity=item.get("entity", ""),
                    claim=item.get("claim", ""),
                    grounded=item.get("baseline_b_plausible") if item.get("baseline_b_plausible") is not None else item.get("grounded"),
                )
            )
        comment_groups.append(group)
    return comment_groups


def load_comment_records_from_outputs(output_dir: Path) -> List[CommentRecord]:
    """Flatten grouped verdicts back into a single comment list."""

    return [comment for group in load_comment_groups_from_outputs(output_dir) for comment in group]


def load_comment_groups_from_review_inputs(input_dir: Path) -> List[List[CommentRecord]]:
    """Load review-agent JSON files into comment groups for scoring."""

    comment_groups: List[List[CommentRecord]] = []
    for input_path in sorted(input_dir.glob("*.json")):
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        group: List[CommentRecord] = []
        for item in payload.get("comments", []):
            group.append(
                CommentRecord(
                    file=item.get("file", ""),
                    line=int(item.get("line", 0)),
                    entity=item.get("entity", ""),
                    claim=item.get("claim", ""),
                    grounded=item.get("grounded"),
                )
            )
        comment_groups.append(group)
    return comment_groups


def score_comment_groups(comment_groups: List[List[CommentRecord]], bugs: List[InjectionRecord], verifier_enabled: bool = False) -> List[Any]:
    """Compute one metrics object per review-output file from the grouped comments."""

    run_metrics = []
    for group in comment_groups:
        # Filter the global bug list to only those that could apply to this comment group
        # (matching by file name). This ensures FN counts are per-run, not across the whole dataset.
        file_names = {Path(comment.file).name.lower() for comment in group if comment.file}
        bugs_for_group = [bug for bug in bugs if Path(bug.file).name.lower() in file_names]

        classifications = classify_comments(group, bugs_for_group)
        # compute_metrics expects the bugs relevant to this run so FN reflects missed bugs for this file
        run_metrics.append(compute_metrics(classifications, bugs_for_group, verifier_enabled=verifier_enabled))

    return run_metrics


def score_system(comments: List[CommentRecord], bugs: List[Any]) -> Dict[str, Any]:
    """Compute per-run metrics and aggregate summary for one system."""

    classifications = classify_comments(comments, bugs)
    metrics = compute_metrics(classifications, bugs, verifier_enabled=False)
    return {
        "metrics": metrics,
        "classifications": classifications,
    }


def summarize_metrics(run_metrics: List[Any]) -> Dict[str, float]:
    """Aggregate metrics across three runs with mean and std."""
    precisions = [item.precision for item in run_metrics]
    recalls = [item.recall for item in run_metrics]
    f1s = [item.f1 for item in run_metrics]
    hallucination_rates = [item.hallucination_rate for item in run_metrics]

    # Grounding-side values (may be None when not applicable)
    grounding_values = [getattr(item, "grounding_accuracy", None) for item in run_metrics if getattr(item, "grounding_accuracy", None) is not None]
    hallucination_catch_rates = [getattr(item, "hallucination_catch_rate", None) for item in run_metrics if getattr(item, "hallucination_catch_rate", None) is not None]
    false_grounding_rates = [getattr(item, "false_grounding_rate", None) for item in run_metrics if getattr(item, "false_grounding_rate", None) is not None]
    grounding_precisions = [getattr(item, "grounding_precision", None) for item in run_metrics if getattr(item, "grounding_precision", None) is not None]

    # Micro-averaged recall across runs: sum TP / sum (TP + FN)
    total_tp = sum(item.tp for item in run_metrics)
    total_fn = sum(item.fn for item in run_metrics)
    recall_micro = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) else 0.0

    return {
        "precision_mean": mean(precisions),
        "precision_std": pstdev(precisions) if len(precisions) > 1 else 0.0,
        "recall_mean": recall_micro,
        "recall_std": pstdev(recalls) if len(recalls) > 1 else 0.0,
        "f1_mean": mean(f1s),
        "f1_std": pstdev(f1s) if len(f1s) > 1 else 0.0,
        "hallucination_rate_mean": mean(hallucination_rates),
        "hallucination_rate_std": pstdev(hallucination_rates) if len(hallucination_rates) > 1 else 0.0,
        "grounding_accuracy_mean": mean(grounding_values) if grounding_values else None,
        "grounding_accuracy_std": pstdev(grounding_values) if len(grounding_values) > 1 else 0.0 if grounding_values else None,
        "hallucination_catch_rate_mean": mean(hallucination_catch_rates) if hallucination_catch_rates else None,
        "hallucination_catch_rate_std": pstdev(hallucination_catch_rates) if len(hallucination_catch_rates) > 1 else 0.0 if hallucination_catch_rates else None,
        "false_grounding_rate_mean": mean(false_grounding_rates) if false_grounding_rates else None,
        "false_grounding_rate_std": pstdev(false_grounding_rates) if len(false_grounding_rates) > 1 else 0.0 if false_grounding_rates else None,
        "grounding_precision_mean": mean(grounding_precisions) if grounding_precisions else None,
        "grounding_precision_std": pstdev(grounding_precisions) if len(grounding_precisions) > 1 else 0.0 if grounding_precisions else None,
    }


def write_results_table(results: Dict[str, Any], output_path: Path) -> None:
    """Write a markdown table and CSV file for the aggregated results."""

    rows = []
    for system_name, payload in results.items():
        if payload.get("available") is False:
            rows.append(
                {
                    "system": system_name,
                    "precision": "N/A",
                    "recall": "N/A",
                    "f1": "N/A",
                    "hallucination_rate": "N/A",
                    "grounding_accuracy": "N/A",
                }
            )
            continue
        summary = payload["summary"]
        rows.append(
            {
                "system": system_name,
                "precision": f"{summary['precision_mean']:.3f} ± {summary['precision_std']:.3f}",
                "recall": f"{summary['recall_mean']:.3f} ± {summary['recall_std']:.3f}",
                "f1": f"{summary['f1_mean']:.3f} ± {summary['f1_std']:.3f}",
                "hallucination_rate": f"{summary['hallucination_rate_mean']:.3f} ± {summary['hallucination_rate_std']:.3f}",
                "grounding_accuracy": "N/A",
            }
        )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["system", "precision", "recall", "f1", "hallucination_rate", "grounding_accuracy"])
        writer.writeheader()
        writer.writerows(rows)

    md_path = output_path.with_suffix(".md")
    with md_path.open("w", encoding="utf-8") as handle:
        handle.write("| system | precision | recall | f1 | hallucination_rate | grounding_accuracy |\n")
        handle.write("| --- | --- | --- | --- | --- | --- |\n")
        for row in rows:
            handle.write(f"| {row['system']} | {row['precision']} | {row['recall']} | {row['f1']} | {row['hallucination_rate']} | {row['grounding_accuracy']} |\n")


def build_proposed_outputs(review_input_dir: Path, output_dir: Path) -> List[Path]:
    """Verify all review comments and write grounded Proposed outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []

    for input_path in sorted(review_input_dir.glob("*.json")):
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        comments = []
        for item in payload.get("comments", []):
            verification = verify_comment(item)
            comment_copy = dict(item)
            comment_copy["grounded"] = verification["status"] == "grounded"
            comments.append(comment_copy)

        output_payload = {"comments": comments}
        output_path = output_dir / input_path.name
        output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        written_files.append(output_path)

    return written_files


def main() -> None:
    artifact_path = REPO_ROOT / "scale_up_results.json"
    injection_log_path = REPO_ROOT / "code_review_project" / "ground_truth" / "injection_log.json"

    output_dir = REPO_ROOT / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    bugs = load_injection_log(injection_log_path)

    review_inputs_dir = output_dir / "review_inputs"
    baseline_b_outputs_dir = output_dir / "baseline_b_outputs"
    proposed_outputs_dir = output_dir / "proposed_outputs"

    results: Dict[str, Any] = {}

    if artifact_path.exists():
        artifact = load_scale_up_artifact(artifact_path)
        write_review_inputs_from_artifact(artifact, review_inputs_dir)
        print(f"Prepared {len(list(review_inputs_dir.glob('*.json')))} review input files from {artifact_path}")
    else:
        print(f"No scale-up artifact found at {artifact_path}; skipping evaluation")

    if review_inputs_dir.exists() and any(review_inputs_dir.glob("*.json")):
        baseline_a_groups = load_comment_groups_from_review_inputs(review_inputs_dir)
        if baseline_a_groups:
            baseline_a_metrics = score_comment_groups(baseline_a_groups, bugs, verifier_enabled=False)
            summary = summarize_metrics(baseline_a_metrics)
            serializable_run_metrics = [
                {
                    "tp": item.tp,
                    "fp": item.fp,
                    "fn": item.fn,
                    "total_comments": item.total_comments,
                    "precision": item.precision,
                    "recall": item.recall,
                    "f1": item.f1,
                    "hallucination_rate": item.hallucination_rate,
                    "grounding_accuracy": item.grounding_accuracy,
                    "hallucination_catch_rate": getattr(item, "hallucination_catch_rate", None),
                    "false_grounding_rate": getattr(item, "false_grounding_rate", None),
                    "grounding_precision": getattr(item, "grounding_precision", None),
                }
                for item in baseline_a_metrics
            ]
            results["Baseline A"] = {
                "available": True,
                "summary": summary,
                "run_metrics": serializable_run_metrics,
            }
        else:
            results["Baseline A"] = {"available": False}

        proposed_written = build_proposed_outputs(review_inputs_dir, proposed_outputs_dir)
        print(f"Wrote {len(proposed_written)} Proposed outputs")

        proposed_groups = load_comment_groups_from_outputs(proposed_outputs_dir)
        if proposed_groups:
            proposed_metrics = score_comment_groups(proposed_groups, bugs, verifier_enabled=True)
            summary = summarize_metrics(proposed_metrics)
            serializable_run_metrics = [
                {
                    "tp": item.tp,
                    "fp": item.fp,
                    "fn": item.fn,
                    "total_comments": item.total_comments,
                    "precision": item.precision,
                    "recall": item.recall,
                    "f1": item.f1,
                    "hallucination_rate": item.hallucination_rate,
                    "grounding_accuracy": item.grounding_accuracy,
                    "hallucination_catch_rate": getattr(item, "hallucination_catch_rate", None),
                    "false_grounding_rate": getattr(item, "false_grounding_rate", None),
                    "grounding_precision": getattr(item, "grounding_precision", None),
                }
                for item in proposed_metrics
            ]
            results["Proposed"] = {
                "available": True,
                "summary": summary,
                "run_metrics": serializable_run_metrics,
            }
        else:
            results["Proposed"] = {"available": False}

        written_outputs = build_baseline_b_outputs(review_inputs_dir, baseline_b_outputs_dir, REPO_ROOT)
        print(f"Wrote {len(written_outputs)} Baseline B outputs")

        baseline_b_groups = load_comment_groups_from_outputs(baseline_b_outputs_dir)
        if baseline_b_groups:
            # enable verifier-aware labeling so grounding-side metrics are computed
            baseline_b_metrics = score_comment_groups(baseline_b_groups, bugs, verifier_enabled=True)
            summary = summarize_metrics(baseline_b_metrics)
            serializable_run_metrics = [
                {
                    "tp": item.tp,
                    "fp": item.fp,
                    "fn": item.fn,
                    "total_comments": item.total_comments,
                    "precision": item.precision,
                    "recall": item.recall,
                    "f1": item.f1,
                    "hallucination_rate": item.hallucination_rate,
                    "grounding_accuracy": item.grounding_accuracy,
                    "hallucination_catch_rate": getattr(item, "hallucination_catch_rate", None),
                    "false_grounding_rate": getattr(item, "false_grounding_rate", None),
                    "grounding_precision": getattr(item, "grounding_precision", None),
                }
                for item in baseline_b_metrics
            ]
            results["Baseline B"] = {
                "available": True,
                "summary": summary,
                "run_metrics": serializable_run_metrics,
            }
        else:
            results["Baseline B"] = {"available": False}
    else:
        results["Baseline A"] = {"available": False, "reason": "No scale-up review inputs were generated."}
        results["Baseline B"] = {"available": False, "reason": "No scale-up review inputs were generated."}
        results["Proposed"] = {"available": False, "reason": "No scale-up review inputs were generated."}

    write_results_table(results, output_dir / "results_table.csv")
    with (output_dir / "evaluation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    print("Saved evaluation outputs to", output_dir)


if __name__ == "__main__":
    main()
