from __future__ import annotations

from math import comb
from typing import List, Tuple


def compute_mcnemar_table(baseline_right: List[bool], proposed_right: List[bool]) -> Tuple[int, int, int, int]:
    """Build a 2x2 McNemar table from paired per-file correctness indicators."""

    a = b = c = d = 0
    for base_ok, prop_ok in zip(baseline_right, proposed_right):
        if base_ok and prop_ok:
            a += 1
        elif base_ok and not prop_ok:
            b += 1
        elif not base_ok and prop_ok:
            c += 1
        else:
            d += 1
    return a, b, c, d


def exact_mcnemar_test(baseline_right: List[bool], proposed_right: List[bool]) -> Tuple[float, int, int, int]:
    """Return the exact two-sided p-value for McNemar's test using the binomial distribution."""

    a, b, c, d = compute_mcnemar_table(baseline_right, proposed_right)
    discordant = b + c
    if discordant == 0:
        return 1.0, b, c, d

    min_discordant = min(b, c)
    # Sum the two binomial tails (k <= min_discordant and k >= discordant - min_discordant)
    p_value = min(1.0, 2.0 * sum(comb(discordant, k) * (0.5**discordant) for k in range(0, min_discordant + 1)))
    return p_value, b, c, d


def bootstrap_confidence_interval(values: List[float], confidence: float = 0.95, n_bootstrap: int = 2000) -> Tuple[float, float]:
    """Fallback bootstrap confidence interval for the difference in accuracy when the table is sparse."""

    import random

    if not values:
        return 0.0, 0.0

    rng = random.Random(42)
    deltas = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(values) for _ in range(len(values))]
        deltas.append(sum(sample) / len(sample))
    lower = (1 - confidence) / 2
    upper = 1 - lower
    ordered = sorted(deltas)
    return ordered[int(len(ordered) * lower)], ordered[int(len(ordered) * upper)]
