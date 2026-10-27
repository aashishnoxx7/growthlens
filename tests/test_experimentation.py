"""
Tests for growthlens.experimentation module.
Verifies sample size formulas, two-proportion z-tests, Wilson score intervals,
and simulation reproducibility.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from growthlens.experimentation import (
    EXPERIMENT_DISCLAIMER,
    diff_proportion_ci,
    required_sample_size,
    run_simulated_experiment,
    two_proportion_ztest,
    wilson_ci,
)


def test_required_sample_size_increases_with_smaller_mde():
    # Detecting a 1pp difference requires a much larger sample than detecting a 5pp difference
    n_small_mde = required_sample_size(baseline_rate=0.05, mde=0.01, alpha=0.05, power=0.80)
    n_large_mde = required_sample_size(baseline_rate=0.05, mde=0.05, alpha=0.05, power=0.80)
    assert n_small_mde > n_large_mde


def test_required_sample_size_invalid_inputs():
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=0.0, mde=0.02)
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=1.0, mde=0.02)
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=0.05, mde=-0.01)
    with pytest.raises(ValueError):
        required_sample_size(baseline_rate=0.05, mde=0.01, alpha=1.5)


def test_wilson_ci_valid_bounds():
    # 50 conversions out of 100 trials (50%)
    low, high = wilson_ci(50, 100, confidence=0.95)
    assert 0.0 <= low < 0.5 < high <= 1.0
    # Wilson interval for 50/100 should be approx [0.4038, 0.5962]
    assert low == pytest.approx(0.4038, abs=0.01)
    assert high == pytest.approx(0.5962, abs=0.01)


def test_wilson_ci_zero_trials():
    low, high = wilson_ci(0, 0)
    assert (low, high) == (0.0, 1.0)


def test_two_proportion_ztest_identical_rates():
    # 50/1000 vs 50/1000 -> z = 0, p-value = 1.0
    z, p_val = two_proportion_ztest(1000, 50, 1000, 50)
    assert z == pytest.approx(0.0)
    assert p_val == pytest.approx(1.0)


def test_two_proportion_ztest_distinct_rates():
    # 50/1000 (5%) vs 100/1000 (10%) -> strongly significant
    z, p_val = two_proportion_ztest(1000, 50, 1000, 100)
    assert z > 3.0
    assert p_val < 0.001


def test_run_simulated_experiment_reproducible():
    res1 = run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.08, n_per_arm=5000, seed=123)
    res2 = run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.08, n_per_arm=5000, seed=123)
    
    assert res1["simulated"]["ctrl_conversions"] == res2["simulated"]["ctrl_conversions"]
    assert res1["simulated"]["treat_conversions"] == res2["simulated"]["treat_conversions"]
    assert res1["statistics"]["p_value"] == res2["statistics"]["p_value"]


def test_run_simulated_experiment_significant():
    # Large sample and substantial effect should detect significance
    res = run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.10, n_per_arm=10000, seed=42)
    assert res["statistics"]["significant"] is True
    assert res["statistics"]["p_value"] < 0.01


def test_run_simulated_experiment_disclaimer_present():
    res = run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.06, n_per_arm=1000, seed=42)
    assert "SIMULATED EXPERIMENT" in res["disclaimer"]
    assert "disclaimer" in res


def test_experiment_invalid_inputs():
    with pytest.raises(ValueError):
        run_simulated_experiment(baseline_rate=0.0, treatment_rate=0.05, n_per_arm=1000)
    with pytest.raises(ValueError):
        run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.05, n_per_arm=1)


def test_absolute_diff_calculation():
    res = run_simulated_experiment(baseline_rate=0.05, treatment_rate=0.08, n_per_arm=5000, seed=42)
    sim = res["simulated"]
    expected_diff = (sim["obs_treat_rate"] - sim["obs_ctrl_rate"]) * 100
    assert res["statistics"]["abs_diff_pp"] == pytest.approx(expected_diff, abs=0.001)
