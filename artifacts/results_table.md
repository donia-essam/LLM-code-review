# End-to-End System Evaluation & Grounding Comparison

This table presents the core experimental comparison across the three system variants evaluated on the full benchmark suite (~240 files across 3 runs).

## 1. End-to-End Code Review System Performance

| System Variant | Review Paradigm | Filtered Emitted Comments | Precision | Recall (Micro) | F1 Score | Hallucination Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline A** | Unverified Single-Shot Reviewer | 730 | 0.143 ± 0.346 | 0.086 ± 0.185 | 0.107 ± 0.224 | 0.858 ± 0.346 |
| **Baseline B** | Reference-Free LLM-Judge Filter | 730 | 0.143 ± 0.346 | 0.086 ± 0.185 | 0.107 ± 0.224 | 0.858 ± 0.346 |
| **Proposed** | Static-Analysis Grounded Verifier | 34 | **1.000 ± 0.000** | 0.028 ± 0.165 | 0.055 ± 0.228 | **0.000 ± 0.000** |

---

## 2. Hallucination Detection & Grounding Subsystem Performance (RQ1)

| Subsystem / Detector | Evaluated Claims | TP Retention (Grounding Accuracy) | Hallucination Catch Rate (Sensitivity) | Hallucination Leak (False Grounding Rate) | Grounding Precision |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline B Proxy Judge** | 730 | 100.0% (104/104) | 0.0% (0/626) | 100.0% (626/626) | 14.25% (104/730) |
| **Proposed Grounded Verifier** | 730 | 32.69% (34/104) | **100.0% (626/626)** | **0.0% (0/626)** | **100.0% (34/34)** |
