# DeepSeek Flash vs Kimi K2.6 — Verification Comparison

## 1. Purpose

This document compares the two LLMs evaluated on the same 180-file code-review benchmark:

1. **DeepSeek V4 Flash**
2. **Kimi K2.6**

The same verifier was applied to both model outputs.

## 2. Overall Verification Results

| Metric | DeepSeek V4 Flash | Kimi K2.6 |
|---|---:|---:|
| Total benchmark files | 180 | 180 |
| Total claims | **125** | **67** |
| Grounded claims | **107** | **52** |
| Non-grounded / Hallucinated | **18** | **15** |
| File not found | 0 | 0 |
| Invalid input | 0 | 0 |
| Grounding rate | **85.6%** | **77.6%** |
| Non-grounded rate | **14.4%** | **22.4%** |

DeepSeek Flash generated substantially more claims than Kimi (125 vs 67). Therefore, grounding rate should not be interpreted as a complete measure of model quality by itself.

## 3. Claim-Type Comparison

### DeepSeek V4 Flash

| Claim Type | Total | Grounded | Grounding Rate |
|---|---:|---:|---:|
| `null_safety_violation` | 41 | 36 | **87.8%** |
| `off_by_one_bound` | 43 | 34 | **79.1%** |
| `unused_variable` | 41 | 37 | **90.2%** |
| **Total** | **125** | **107** | **85.6%** |

### Kimi K2.6

| Claim Type | Total | Grounded | Grounding Rate |
|---|---:|---:|---:|
| `null_safety_violation` | 24 | 21 | **87.5%** |
| `off_by_one_bound` | 5 | 0 | **0.0%** |
| `unused_variable` | 38 | 31 | **81.6%** |
| **Total** | **67** | **52** | **77.6%** |

Both models had very similar grounding rates for null-safety. DeepSeek Flash was stronger on unused-variable and especially on the observed off-by-one claims.

## 4. Raw Claims by Dataset

| Dataset | DeepSeek Flash | Kimi K2.6 |
|---|---:|---:|
| `clean` | 2 | 2 |
| `clean_negative_controls` | 8 | 6 |
| `mutated` | 36 | 38 |
| `mutated_null` | 36 | 21 |
| `mutated_offbyone` | 35 | 0 |

For Kimi, all 36 `mutated_offbyone` files were processed, but no claims were generated from that subset. This confirms that the zero is model behavior rather than skipped input.

## 5. Localization Comparison

Localization used two independent AST-based checks:

- **Entity exists:** whether the reported entity can be found in the parsed source.
- **Line match:** whether the reported line corresponds to the identified entity/source location.

| Check | DeepSeek Flash | Kimi K2.6 |
|---|---:|---:|
| Entity exists | **119/125 = 95.2%** | **66/67 = 98.5%** |
| Line match | **119/125 = 95.2%** | **58/67 = 86.6%** |

Kimi was slightly better at selecting an entity that exists in the source, while DeepSeek Flash was better at precise source-line localization.

## 6. Kimi Localization by Claim Type

| Claim Type | Total | Entity Exists | Line Match |
|---|---:|---:|---:|
| `null_safety_violation` | 24 | 24 (100%) | 22 (91.7%) |
| `off_by_one_bound` | 5 | 4 (80.0%) | 5 (100%) |
| `unused_variable` | 38 | 38 (100%) | 31 (81.6%) |
| **Total** | **67** | **66 (98.5%)** | **58 (86.6%)** |

Entity and line checks are independent; a claim can pass one and fail the other.

## 7. Negative-Control Behavior

| Dataset | DeepSeek Flash Claims | Kimi Claims |
|---|---:|---:|
| `clean` | 2 | 2 |
| `clean_negative_controls` | 8 | 6 |

For Kimi, 5 of the 6 claims generated on `clean_negative_controls` were non-grounded.

## 8. Overall Takeaway

### DeepSeek V4 Flash

- Generated more claims: **125**
- Higher overall grounding rate: **85.6%**
- Better line localization: **95.2%**
- Produced claims on the `mutated_offbyone` subset

### Kimi K2.6

- Generated fewer claims: **67**
- Grounding rate: **77.6%**
- Higher entity-existence rate: **98.5%**
- Lower line-match rate: **86.6%**
- Strong null-safety grounding: **87.5%**
- Weaker observed off-by-one behavior: **0/5 grounded**
- Generated no claims from the 36 `mutated_offbyone` files

## 9. Conclusion

The experiment does not establish that one model is universally better at every aspect. DeepSeek Flash was more productive and had higher overall grounding and line-localization rates, while Kimi was more conservative and had a slightly higher entity-existence rate.

The comparison should therefore be presented as a **comparative grounding and error profile**, not as a single accuracy ranking.