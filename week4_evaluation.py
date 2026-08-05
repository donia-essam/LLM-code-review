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
    """Load Baseline B verdicts from each per-file JSON output into a separate comment group."""

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
                    grounded=item.get("baseline_b_plausible"),
                )
            )
        comment_groups.append(group)
    return comment_groups


def load_comment_records_from_outputs(output_dir: Path) -> List[CommentRecord]:
    """Flatten grouped Baseline B verdicts back into a single comment list."""

    return [comment for group in load_comment_groups_from_outputs(output_dir) for comment in group]


def score_comment_groups(comment_groups: List[List[CommentRecord]], bugs: List[InjectionRecord]) -> List[Any]:
    """Compute one metrics object per review-output file from the grouped comments."""

    run_metrics = []
    for group in comment_groups:
        classifications = classify_comments(group, bugs)
        run_metrics.append(compute_metrics(classifications, bugs, verifier_enabled=False))

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

    return {
        "precision_mean": mean(precisions),
        "precision_std": pstdev(precisions) if len(precisions) > 1 else 0.0,
        "recall_mean": mean(recalls),
        "recall_std": pstdev(recalls) if len(recalls) > 1 else 0.0,
        "f1_mean": mean(f1s),
        "f1_std": pstdev(f1s) if len(f1s) > 1 else 0.0,
        "hallucination_rate_mean": mean(hallucination_rates),
        "hallucination_rate_std": pstdev(hallucination_rates) if len(hallucination_rates) > 1 else 0.0,
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


def main() -> None:
    artifact_path = REPO_ROOT / "scale_up_results.json"
    injection_log_path = REPO_ROOT / "code_review_project" / "ground_truth" / "injection_log.json"

    output_dir = REPO_ROOT / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    bugs = load_injection_log(injection_log_path)

    review_inputs_dir = output_dir / "review_inputs"
    baseline_b_inputs_dir = output_dir / "baseline_b_inputs"
    baseline_b_outputs_dir = output_dir / "baseline_b_outputs"

    results: Dict[str, Any] = {}

    if artifact_path.exists():
        artifact = load_scale_up_artifact(artifact_path)
        write_review_inputs_from_artifact(artifact, review_inputs_dir)
        print(f"Prepared {len(list(review_inputs_dir.glob('*.json')))} review input files from {artifact_path}")
    else:
        print(f"No scale-up artifact found at {artifact_path}; skipping Baseline B run")

    if review_inputs_dir.exists() and any(review_inputs_dir.glob("*.json")):
        written_outputs = build_baseline_b_outputs(review_inputs_dir, baseline_b_outputs_dir, REPO_ROOT)
        print(f"Wrote {len(written_outputs)} Baseline B outputs")

        comment_groups = load_comment_groups_from_outputs(baseline_b_outputs_dir)
        run_metrics = []
        if comment_groups:
            run_metrics = score_comment_groups(comment_groups, bugs)
            summary = summarize_metrics(run_metrics)
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
                }
                for item in run_metrics
            ]
            results["Baseline B"] = {
                "available": True,
                "summary": summary,
                "run_metrics": serializable_run_metrics,
            }
        else:
            results["Baseline B"] = {"available": False}
    else:
        results["Baseline B"] = {"available": False}

    results["Baseline A"] = {"available": False, "reason": "No dedicated Baseline A output artifact was found in the repository."}
    results["Proposed"] = {"available": False, "reason": "No dedicated Proposed output artifact was found in the repository."}

    write_results_table(results, output_dir / "results_table.csv")
    with (output_dir / "evaluation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    print("Saved evaluation outputs to", output_dir)


if __name__ == "__main__":
    main()
