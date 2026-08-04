# Baseline B LLM-Judge Design

## 1. Repository findings

### 1.1 Reviewer schema used by Baseline A
The existing reviewer in [review_agent.py](review_agent.py) emits a compact JSON object with this schema:

```json
{
  "comments": [
    {
      "file": "string",
      "line": 0,
      "entity": "string",
      "claim": "string"
    }
  ]
}
```

The concrete Pydantic schema in [review_agent.py](review_agent.py) is:

- `file: str`
- `line: int`
- `entity: str`
- `claim: str`

The allowed values for `claim` are:

- `unused_variable`
- `null_safety_violation`
- `off_by_one_bound`

The example payload in [review_results.json](review_results.json) confirms this exact shape.

### 1.2 How source context is already represented in this repo
The repository already has a function-level source catalog in [code_review_project/ground_truth/function_catalog.json](code_review_project/ground_truth/function_catalog.json). Each entry contains:

- `file`
- `function`
- `line`
- `snippet`
- `num_lines`

This comes from the AST-based scan in [code_review_project/tools/scan_algorithms.py](code_review_project/tools/scan_algorithms.py), which extracts function snippets directly from the source tree. The target-selection logic in [code_review_project/tools/select_files.py](code_review_project/tools/select_files.py) also assumes a file-plus-function representation.

### 1.3 Practical implication for Baseline B
Baseline B should not rely on the reviewer’s `claim` as ground truth. Instead, it should receive:

1. the review comment payload (`file`, `line`, `entity`, `claim`), and
2. the relevant code context for that file/line.

The most natural retrieval strategy is:

- resolve the comment’s `file` against the repository source tree under [code_review_project/data/clean/algorithms/algorithms](code_review_project/data/clean/algorithms/algorithms),
- read the source file,
- extract the enclosing function snippet when possible, and
- if that function is already known from the catalog, prefer the existing `snippet` entry for that function.

### 1.4 How this maps to the scoring pipeline
The scoring models in [scoring/models.py](scoring/models.py) define a `CommentRecord` with:

- `file`
- `line`
- `entity`
- `claim`
- `grounded` (optional bool)

The classifier in [scoring/classifier.py](scoring/classifier.py) uses the injection log to determine whether a comment is a true positive, and it only uses `grounded` for verifier-style logic. That means Baseline B’s verdict should be treated as a system-specific plausibility judgment, not as a replacement for the injection-log-based TP/FP/FN logic.

---

## 2. Baseline B judge prompt template

### 2.1 Goal
Judge whether the review comment is plausibly consistent with the provided code snippet, using only the comment and the code context. Do not use the hidden bug list, injection log, or any external ground-truth signal.

### 2.2 System prompt

```text
You are an independent code-review plausibility judge.

Your task is to decide whether a review comment is reasonably consistent with the provided code snippet.
You are not given any hidden ground truth, injection log, or bug list.
Judge only based on the comment and the code evidence.

Focus on whether the named entity and the stated claim could plausibly be supported by the code at the indicated location.
Be conservative when the evidence is weak or ambiguous.

Return strict JSON only with this schema:
{
  "plausible": boolean,
  "confidence": number,
  "reasoning": string
}
```

### 2.3 User message template

```text
Review comment details:
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
```

### 2.4 Why this prompt is aligned to the project
- It never asks the judge to identify the true bug type.
- It never uses the injection log or hidden labels.
- It keeps the task narrow: plausibility/consistency with the code, not truth verification.

---

## 3. Structured JSON output schema

### 3.1 Output shape

Use a single parseable object:

```json
{
  "plausible": true,
  "confidence": 0.82,
  "reasoning": "The code shows a likely null dereference risk because the variable is used without a prior None check."
}
```

### 3.2 Field definitions
- `plausible`: boolean
  - `true` if the comment seems reasonably consistent with the code.
  - `false` if the code does not support the comment.
- `confidence`: float
  - A value in $[0,1]$.
  - Use a calibrated score rather than an arbitrary 0/1 label.
- `reasoning`: string
  - A short explanation of the evidence and why the verdict was reached.

This keeps the output simple, parseable, and consistent with the project’s “structured output over free text” principle.

---

## 4. Default code context size

### 4.1 Recommended default
Use the enclosing function snippet as the default context window.

If no enclosing function can be determined, fall back to a local window of roughly 12 lines before and after the target line.

### 4.2 Rationale
- For these bug classes, the relevant evidence is usually local to the enclosing function.
- A function-level snippet gives enough surrounding context to judge whether an unused-variable warning, a null-safety claim, or an off-by-one bound claim is actually supported.
- It is a good tradeoff between accuracy and cost.

### 4.3 Tradeoff
- More context improves judgment quality and reduces false positives.
- More context also increases token usage and latency.
- The function-level default is a good compromise for this project because the repository already provides function-level snippets in the catalog.

### 4.4 Practical implementation rule
- Preferred: use the function snippet from the catalog when available.
- Fallback: if the file/line does not map cleanly to a function snippet, use a local window around the target line.
- Avoid giving the whole file by default unless the function is very short and the file is small; whole-file context is usually unnecessary and more expensive.

---

## 5. How this should map to the current scoring pipeline

### 5.1 Important scope decision
Baseline B is a reference-free plausibility detector. It should not be treated as a hidden-ground-truth verifier.

### 5.2 Recommended mapping
For Baseline B, the judge’s `plausible` verdict should be treated as this system’s own consistency judgment, not as a replacement for the injection-log-based truth label.

In other words:
- `plausible = true` means “this comment looks consistent with the code.”
- `plausible = false` means “this comment looks inconsistent or unsupported by the code.”
- It does not mean “this is a true positive” in the scoring pipeline.

### 5.3 Why this matters
The existing scoring flow in [scoring/classifier.py](scoring/classifier.py) decides TP/FP/FN by matching comments to injected bugs from the injection log. Baseline B does not have that information, so it should not be used to create the project’s primary correctness labels.

### 5.4 Suggested use in the pipeline
When you later wire this into the code:
- keep the Baseline B verdict as a separate system-specific field (for example, `baseline_b_plausible` or a per-system metadata field), or
- temporarily map it into `CommentRecord.grounded` only for analysis of this system’s own consistency behavior,
- but do not let it override the main TP/FP/FN classification logic based on the injection log.

That keeps the evaluation fair and faithful to the project’s stated scope.

---

## 6. Final recommendation

Use a simple, strict three-field JSON schema:

```json
{
  "plausible": true,
  "confidence": 0.8,
  "reasoning": "short explanation"
}
```

Use the enclosing function snippet as the default context, and interpret the result as a plausibility judgment rather than a ground-truth label.
