# RQ3 Breakdown: Performance by Injected Bug Class

This document provides the empirical breakdown for **RQ3**: *Which bug/hallucination types are most and least detectable by static-analysis grounding (unused variables vs. null-safety vs. off-by-one loop bounds), and does this vary by verification method?*

---

## 1. Summary by Bug Class

| Bug Class | Injected Ground Truth Bugs | Candidate Comments Emitted (Baseline A) | True Positives (TP) | False Positives / Hallucinations (FP) | Raw Precision | Raw Hallucination Rate | Verifier Grounding Accuracy (TP Retention) | Verifier Hallucination Catch Rate | Verified Precision (Post-Filter) | Verified Hallucination Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Unused Variables** | 60 | 646 | 36 | 610 | 5.57% | 94.43% | **94.44%** (34/36) | **100.00%** (610/610) | **100.00%** | **0.00%** |
| **Null Safety** | 60 | 41 | 34 | 7 | 82.93% | 17.07% | **0.00%** (0/34) | **100.00%** (7/7) | N/A (0 passed) | 0.00% |
| **Off-by-One Bounds** | 60 | 43 | 34 | 9 | 79.07% | 20.93% | **0.00%** (0/34) | **100.00%** (9/9) | N/A (0 passed) | 0.00% |
| **Overall Aggregate** | **180** | **730** | **104** | **626** | **14.25%** | **85.75%** | **32.69%** (34/104) | **100.00%** (626/626) | **100.00%** (34/34) | **0.00%** (0/34) |

---

## 2. Key Findings for RQ3

1. **Most Detectable & Verifiable Class**:
   - **`unused_variable`** achieved **94.44% grounding accuracy** and **100% hallucination rejection**. The deterministic AST and `pyflakes` cross-check reliably verified real unused variables while eliminating 610 hallucinated claims.
2. **Hardest Classes for Static Verifiers**:
   - **`null_safety`** and **`off_by_one`** suffered from strict static checker limitations in isolated standalone files without complete type stubs or inter-procedural context, resulting in conservative rejections.
3. **Hallucination Characteristics**:
   - The unverified LLM reviewer produced massive hallucination volume on `unused_variable` (94.43% hallucination rate) due to speculative scoping assumptions, whereas it was much more conservative on semantic logic bugs (`null_safety`: 17.07%, `off_by_one`: 20.93%).
