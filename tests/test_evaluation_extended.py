from __future__ import annotations

import pytest
from scoring.stats import compute_mcnemar_table, exact_mcnemar_test, bootstrap_confidence_interval
from scoring.models import CommentRecord, InjectionRecord
from scoring.matcher import match_comment_to_bug, _normalize_bug_type


def test_normalize_bug_type():
    assert _normalize_bug_type("unused_variable") == "unused_variable"
    assert _normalize_bug_type("null_safety_violation") == "null_safety"
    assert _normalize_bug_type("off_by_one_bound") == "off_by_one"


def test_mcnemar_exact_tails():
    # Symmetric discordant pairs
    p_val, b, c, d = exact_mcnemar_test([True, False], [False, True])
    assert b == 1 and c == 1
    assert p_val == 1.0

    # Highly discordant pairs
    base = [True] * 5 + [False] * 50
    prop = [False] * 5 + [True] * 50
    p_val, b, c, d = exact_mcnemar_test(base, prop)
    assert p_val < 0.001


def test_bootstrap_ci():
    values = [1.0] * 80 + [0.0] * 20
    lower, upper = bootstrap_confidence_interval(values, confidence=0.95, n_bootstrap=1000)
    assert 0.70 <= lower <= upper <= 0.90
