# Verifier Results

## 1. Overview

The verifier validates LLM-generated code review claims against the source code using AST-based checks and static analysis.

For each claim, the verifier checks the reported source location and entity, then performs a claim-specific static verification to determine whether the claim is grounded in the code.

## 2. Full-Scale Verification

The verifier was evaluated on the full-scale LLM review output.

- Total runs/files: 180
- Total claims: 125
- Grounded claims: 107
- Non-grounded claims: 18
- File-not-found: 0
- Invalid-input: 0

### Claim Breakdown

| Claim Type | Total | Grounded | Non-grounded |
|---|---:|---:|---:|
| `null_safety_violation` | 41 | 36 | 5 |
| `off_by_one_bound` | 43 | 34 | 9 |
| `unused_variable` | 41 | 37 | 4 |
| **Total** | **125** | **107** | **18** |

## 3. Localization Validation

The verifier performs AST-based checks to determine whether the entity reported by the LLM exists in the source code and whether the reported source line matches the identified entity.

### Overall Results

| Check | Passed | Total | Rate |
|---|---:|---:|---:|
| Entity exists | 119 | 125 | 95.2% |
| Reported line matches | 119 | 125 | 95.2% |

### Results by Claim Type

| Claim Type | Total | Entity Exists | Line Match |
|---|---:|---:|---:|
| `null_safety_violation` | 41 | 41 (100%) | 38 (92.7%) |
| `off_by_one_bound` | 43 | 37 (86.0%) | 41 (95.3%) |
| `unused_variable` | 41 | 41 (100%) | 40 (97.6%) |

These checks validate the reported entity and location against the parsed source code. They should not be interpreted as independent LLM localization accuracy, since no separately annotated ground-truth localization dataset was used.

## 4. Static Verification

The verifier performs claim-specific static checks to determine whether the reported issue is actually supported by the source code.

- Static checks passed: 107 / 125
- Static check rate: 85.6%

The static checks cover the following claim types:

- `null_safety_violation`
- `off_by_one_bound`
- `unused_variable`

For `off_by_one_bound` claims, the dedicated boundary-mutation check is used as the decisive verification step because the entity reported by the LLM may be contextual rather than the exact AST expression containing the boundary issue.

## 5. Grounding Decision

A claim is considered grounded when the verifier determines that the reported issue is supported by the source code according to the applicable AST and static-analysis checks.

Final result:

- Grounded: 107 / 125 (85.6%)
- Non-grounded: 18 / 125 (14.4%)

The non-grounded claims were retained for error analysis rather than being treated as verified issues.

## 6. Error Analysis

Manual inspection of the non-grounded claims identified several recurring failure modes:

- False-positive bug claims
- Incorrect source-line localization
- Incorrect entity identification
- Incorrect claim-type classification
- Cases where the LLM identified a real issue but reported an incorrect source location

Representative localization issues were observed in claims involving:

- `longest_non_repeat.py`
- `two_sum.py`
- `palindrome_partitioning.py`
- `subsets_unique.py`
- `red_black_tree.py`
- `markov_chain.py`

These cases demonstrate the role of the verifier in distinguishing between an LLM-generated claim and a claim that can actually be grounded in the source code.

## 7. Final Validation

The full-scale verification was rerun after the verifier checks were finalized.

The results remained unchanged:

```text
Total claims: 125
Grounded: 107
Hallucinated: 18
File not found: 0
Invalid input: 0