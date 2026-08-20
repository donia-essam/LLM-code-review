# LLM-Based Code Review Assistant - Review Agent

This repository contains the core LLM-based code review agent developed for **Baseline A** and the **Proposed Pipeline** of the Automated Code Review & Hallucination Detection project.

The agent statically analyzes target Python files using **DeepSeek-v4-Flash (via OpenCode API)** and enforces a strict structural JSON output schema to ensure precise entity tracking and claim verification.

---

##  Features & Scope

* **Target Language:** Python
* **LLM Engine:** DeepSeek-v4-Flash (OpenCode API)
* **Supported Bug Classes:**
  * `unused_variable` (Cross-checked via custom AST parsing)
  * `null_safety_violation` (Cross-checked via custom AST parsing)
  * `off_by_one_bound` (Cross-checked via custom AST parsing)
* **Structured Output:** Strictly outputs JSON data matching a Pydantic schema (`file`, `line`, `entity`, `claim`) without conversational prose or markdown formatting to guarantee seamless integration with Member 3's verifier pipeline.
* **Scale-up Benchmark Scope:** Configured to run batch analysis across target dataset subsets (e.g., 240 files) and automatically output results to `scale_up_results.json`.

---

##  Output Schema

The agent outputs results in the following structure for each reviewed file:

```json
[
  {
    "file_path": "code_review_project/data/mutated/algorithms/bst.py",
    "subdir": "algorithms",
    "run_id": 1,
    "output": {
      "comments": [
        {
          "file": "bst.py",
          "line": 14,
          "entity": "temp_var",
          "claim": "unused_variable"
        }
      ]
    }
  }
]
