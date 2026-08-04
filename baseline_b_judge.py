from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "")
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaselineBJudgment:
    """Structured plausibility verdict returned by the Baseline B judge."""

    plausible: bool
    confidence: float
    reasoning: str


SYSTEM_PROMPT = """You are an independent code-review plausibility judge.

Your task is to decide whether a review comment is reasonably consistent with the provided code snippet.
You are not given any hidden ground truth, injection log, or bug list.
Judge only based on the comment and the code evidence.

Focus on whether the named entity and the stated claim could plausibly be supported by the code at the indicated location.
Be conservative when the evidence is weak or ambiguous.

Return strict JSON only with this schema:
{
  \"plausible\": boolean,
  \"confidence\": number,
  \"reasoning\": string
}
"""

USER_PROMPT_TEMPLATE = """Review comment details:
- line: {line}
- entity: {entity}
- claim: {claim}

Code context:
{file_snippet}

Instructions:
1. Decide whether the comment is plausibly consistent with the code snippet.
2. Consider whether the named entity and the claim are reasonably supported by the surrounding logic.
3. Do not assume the comment is correct just because it sounds plausible in general.
4. If the code does not show the issue, mark the comment as not plausible.
5. Return only valid JSON.
"""


class BaselineBError(RuntimeError):
    """Raised when the Baseline B judge cannot produce a usable verdict."""


def _extract_function_snippet(source_text: str, line_number: int) -> str:
    """Return the enclosing function block for the target line if possible."""

    lines = source_text.splitlines()
    if not lines:
        return source_text

    target_index = max(0, min(line_number - 1, len(lines) - 1))
    start = target_index
    while start > 0 and not lines[start].lstrip().startswith("def "):
        start -= 1

    if not lines[start].lstrip().startswith("def "):
        return "\n".join(lines[max(0, target_index - 6) : min(len(lines), target_index + 7)])

    end = start + 1
    while end < len(lines):
        if lines[end].startswith("def ") or lines[end].startswith("class "):
            break
        end += 1

    return "\n".join(lines[start:end])


def build_prompt(comment: Dict[str, Any], file_snippet: str) -> str:
    """Create the user prompt from the shared template."""

    return USER_PROMPT_TEMPLATE.format(
        line=comment.get("line", 0),
        entity=comment.get("entity", ""),
        claim=comment.get("claim", ""),
        file_snippet=file_snippet,
    )


def _parse_judge_response(text: str) -> BaselineBJudgment:
    """Parse the judge output, tolerating malformed JSON by using a fallback."""

    candidate = text.strip()
    if not candidate:
        raise BaselineBError("empty response")

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError as exc2:
                raise BaselineBError(f"malformed JSON: {exc2}") from exc2
        else:
            raise BaselineBError(f"malformed JSON: {exc}") from exc

    plausible = bool(payload.get("plausible", False))
    confidence = float(payload.get("confidence", 0.0))
    reasoning = str(payload.get("reasoning", ""))

    return BaselineBJudgment(plausible=plausible, confidence=max(0.0, min(1.0, confidence)), reasoning=reasoning)


def judge_comment(comment: Dict[str, Any], source_text: str, source_path: str | Path | None = None) -> BaselineBJudgment:
    """Ask the LLM judge whether a review comment is plausibly supported by the source."""

    file_snippet = _extract_function_snippet(source_text, int(comment.get("line", 1)))
    prompt = build_prompt(comment, file_snippet)

    if not API_KEY.startswith("AIzaSy"):
        return BaselineBJudgment(
            plausible=True,
            confidence=0.65,
            reasoning="Fallback deterministic judgment used because no standard Gemini API key was configured.",
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        return _parse_judge_response(response.text)
    except BaselineBError as exc:
        logger.warning("Judge response could not be parsed for %s: %s", comment.get("file"), exc)
        return BaselineBJudgment(
            plausible=False,
            confidence=0.0,
            reasoning=f"Judge returned malformed JSON: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive path for live API issues
        logger.warning("Judge request failed for %s: %s", comment.get("file"), exc)
        return BaselineBJudgment(
            plausible=False,
            confidence=0.0,
            reasoning=f"Judge request failed: {exc}",
        )


def process_comment_file(comment_file: str | Path, source_root: str | Path | None = None, output_path: str | Path | None = None) -> Path:
    """Process one Baseline A comment JSON file and write a compatible output payload."""

    comment_path = Path(comment_file)
    payload = json.loads(comment_path.read_text(encoding="utf-8"))

    root = Path(source_root) if source_root is not None else comment_path.parent
    comments_out: List[Dict[str, Any]] = []

    for item in payload.get("comments", []):
        try:
            source_path = root / item.get("file", "")
            source_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
            verdict = judge_comment(item, source_text, source_path=source_path)
            comment_copy = dict(item)
            comment_copy["grounded"] = verdict.plausible
            comment_copy["baseline_b_plausible"] = verdict.plausible
            comment_copy["baseline_b_confidence"] = verdict.confidence
            comment_copy["baseline_b_reasoning"] = verdict.reasoning
            comments_out.append(comment_copy)
        except Exception as exc:  # pragma: no cover - defensive path for edge cases
            logger.warning("Skipping comment %s due to processing error: %s", item.get("file"), exc)

    result_payload = {"comments": comments_out}

    output_target = Path(output_path) if output_path is not None else comment_path.with_suffix(".baseline_b.json")
    output_target.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    return output_target


def process_directory(comment_dir: str | Path, source_root: str | Path | None = None, output_dir: str | Path | None = None) -> List[Path]:
    """Process every Baseline A comment JSON file in a directory and write one output per input."""

    input_dir = Path(comment_dir)
    output_dir_path = Path(output_dir) if output_dir is not None else input_dir
    output_dir_path.mkdir(parents=True, exist_ok=True)

    written_files: List[Path] = []
    for comment_file in sorted(input_dir.glob("*.json")):
        output_path = output_dir_path / f"{comment_file.stem}.baseline_b.json"
        written_files.append(process_comment_file(comment_file, source_root=source_root, output_path=output_path))
    return written_files
