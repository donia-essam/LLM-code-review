# Kimi Verifier Results

## 1. Overview

The same verification pipeline used for the DeepSeek Flash benchmark was applied to the Kimi K2.6 review output.

- Model: `kimi-k2.6`
- Input: `scale_up_results_kimi.json`
- Benchmark size: **180 runs/files**
- Datasets: 5 datasets × 36 files each
- Verifier output: `scale_up_verification_results_kimi.json`

The verifier checks the reported file, entity, source line, and claim type using AST-based checks and claim-specific static verification.

## 2. Full-Scale Verification

| Metric | Result |
|---|---:|
| Total claims | **67** |
| Grounded | **52** |
| Non-grounded / Hallucinated | **15** |
| File not found | **0** |
| Invalid input | **0** |
| Grounding rate | **77.6%** |
| Non-grounded rate | **22.4%** |

## 3. Verification by Claim Type

| Claim Type | Total | Grounded | Non-grounded | Grounding Rate |
|---|---:|---:|---:|---:|
| `null_safety_violation` | 24 | 21 | 3 | **87.5%** |
| `off_by_one_bound` | 5 | 0 | 5 | **0.0%** |
| `unused_variable` | 38 | 31 | 7 | **81.6%** |
| **Total** | **67** | **52** | **15** | **77.6%** |

Kimi performed relatively well on null-safety and unused-variable claims. The main observed weakness was `off_by_one_bound`: all 5 generated claims of this type were non-grounded.

## 4. Dataset Coverage

| Dataset | Files Processed | Files With Claims | Claims |
|---|---:|---:|---:|
| `clean` | 36 | 2 | 2 |
| `clean_negative_controls` | 36 | 5 | 6 |
| `mutated` | 36 | 36 | 38 |
| `mutated_null` | 36 | 21 | 21 |
| `mutated_offbyone` | 36 | 0 | 0 |
| **Total** | **180** | **64** | **67** |

All 36 `mutated_offbyone` files were processed, but Kimi generated no claims from any of them. Therefore, the zero claims are not caused by those files being skipped.

## 5. Localization Validation

| Check | Passed | Total | Rate |
|---|---:|---:|---:|
| Entity exists | 66 | 67 | **98.5%** |
| Reported line matches | 58 | 67 | **86.6%** |
| Static verification | 52 | 67 | **77.6%** |

### Localization by Claim Type

| Claim Type | Total | Entity Exists | Line Match |
|---|---:|---:|---:|
| `null_safety_violation` | 24 | 24 (100%) | 22 (91.7%) |
| `off_by_one_bound` | 5 | 4 (80.0%) | 5 (100%) |
| `unused_variable` | 38 | 38 (100%) | 31 (81.6%) |
| **Total** | **67** | **66 (98.5%)** | **58 (86.6%)** |

Entity existence and line matching are separate checks. A claim can have a matching source line while its entity does not pass the entity-existence check.

## 6. Negative Controls

Kimi generated 2 claims on `clean` files and 6 claims on `clean_negative_controls`.

For `clean_negative_controls`:

- 6 claims were generated
- 1 was grounded
- 5 were non-grounded

This indicates false-positive behavior on the negative-control subset.

## 7. Final Result

Kimi K2.6 produced **67 claims**, of which **52 (77.6%)** were grounded by the verifier.

The strongest claim category was `null_safety_violation` at **87.5% grounded**. The main weakness was `off_by_one_bound`, with **0/5 grounded claims**, together with no generated claims from the `mutated_offbyone` subset.

The results were obtained using the same verifier and the same 180-file benchmark used for the DeepSeek comparison.