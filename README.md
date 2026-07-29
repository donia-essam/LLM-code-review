# LLM-Based Code Review Assistant - Review Agent 

This repository contains the core LLM-based code review agent developed for **Baseline A** and the **Proposed Pipeline** of the Automated Code Review & Hallucination Detection project. 

The agent statically analyzes target Python files using `gemini-2.5-flash` and enforces a strict structural JSON output schema to ensure precise entity tracking and claim verification.

---

## Features & Scope

- **Target Language:** Python
- **Supported Bug Classes:**
  1. `unused_variable` (Cross-checked via `pyflakes`)
  2. `null_safety_violation` (Cross-checked via `mypy`)
  3. `off_by_one_bound` (Cross-checked via custom AST parsing)
- **Structured Output:** Strictly outputs JSON data matching a Pydantic schema (`file`, `line`, `entity`, `claim`) without conversational prose to guarantee seamless integration with Member 3's verifier pipeline.
- **API Key Fallback Guard:** Includes a safe mock data injection fallback mechanism to bypass unauthorized environment key constraints during isolated testing.

---

##  Environment Setup

Follow these steps to set up the local environment and run the agent script.

### 1. Prerequisites
Ensure you have Python 3.10+ installed on your system.

### 2. Activate the Virtual Environment
Activate the pre-configured virtual environment in your terminal:
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1