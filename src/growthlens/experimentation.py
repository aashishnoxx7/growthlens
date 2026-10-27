"""
A/B test simulation and statistical calculations for GrowthLens.

ALL results produced by this module are SIMULATED. They do not represent
experiments run by Google, real companies, or actual users.

Statistical methods:
  - Two-proportion z-test for significance testing.
  - Wilson score intervals for confidence intervals.
  - Standard power/sample-size formula for proportions.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import scipy.stats as stats

logger = logging.getLogger(__name__)

EXPERIMENT_DISCLAIMER = (
    "⚠️  SIMULATED EXPERIMENT — These results are generated from random numbers "
    "with user-specified parameters. They do NOT represent a real A/B test, "
    "real user behaviour, or any actual business outcome."
)


# ── Sample size estimation ─────────────────────────────────────────────────────

def required_sample_size(
    baseline_rate: float,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.80,
    two_sided: bool = True,
) -> int:
    """
    Estimate per-arm sample size for a two-proportion test.

    Parameters
    ----------
    baseline_rate : control conversion rate (0–1)
    mde           : minimum detectable effect (absolute pp, e.g. 0.02)
    alpha         : significance threshold (default 0.05)
    power         : desired statistical power (default 0.80)
    two_sided     : use two-sided test (default True)

    Returns
    -------
    int: required sample size per arm (rounded up)

    Formula
    -------
    n = (z_alpha/2 + z_beta)^2 * (p1(1-p1) + p2(1-p2)) / delta^2
    where p2 = p1 + delta.
    """
    if not (0 < baseline_rate < 1):
        raise ValueError("baseline_rate must be strictly between 0 and 1.")
    if mde <= 0:
        raise ValueError("mde must be positive.")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1.")
    if not (0 < power < 1):
        raise ValueError("power must be between 0 and 1.")

    treatment_rate = baseline_rate + mde
    treatment_rate = min(treatment_rate, 0.9999)

    z_alpha = stats.norm.ppf(1 - alpha / (2 if two_sided else 1))
    z_beta = stats.norm.ppf(power)

    p1, p2 = baseline_rate, treatment_rate
    numerator = (z_alpha + z_beta) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
    denominator = (p2 - p1) ** 2

    n = math.ceil(numerator / denominator)
    return n


# ── Confidence intervals ───────────────────────────────────────────────────────

def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """
    Wilson score confidence interval for a proportion.

    Returns (lower, upper) as fractions [0, 1].
    """
    if trials == 0:
        return (0.0, 1.0)
    p_hat = successes / trials
    z = stats.norm.ppf((1 + confidence) / 2)
    denom = 1 + z**2 / trials
    center = (p_hat + z**2 / (2 * trials)) / denom
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / trials + z**2 / (4 * trials**2))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def diff_proportion_ci(
    n_ctrl: int, conv_ctrl: int,
    n_treat: int, conv_treat: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Confidence interval for the difference in proportions (treat - ctrl).
    Uses the normal approximation.
    """
    if n_ctrl == 0 or n_treat == 0:
        return (float("nan"), float("nan"))
    p1 = conv_ctrl / n_ctrl
    p2 = conv_treat / n_treat
    se = math.sqrt(p1 * (1 - p1) / n_ctrl + p2 * (1 - p2) / n_treat)
    z = stats.norm.ppf((1 + confidence) / 2)
    diff = p2 - p1
    return (diff - z * se, diff + z * se)


# ── Hypothesis test ────────────────────────────────────────────────────────────

def two_proportion_ztest(
    n_ctrl: int, conv_ctrl: int,
    n_treat: int, conv_treat: int,
) -> tuple[float, float]:
    """
    Two-sided two-proportion z-test.

    Returns (z_statistic, p_value).
    Uses pooled proportion under H0.
    """
    if n_ctrl == 0 or n_treat == 0:
        return (float("nan"), float("nan"))
    p1 = conv_ctrl / n_ctrl
    p2 = conv_treat / n_treat
    p_pool = (conv_ctrl + conv_treat) / (n_ctrl + n_treat)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_ctrl + 1 / n_treat))
    if se_pool == 0:
        return (float("nan"), float("nan"))
    z = (p2 - p1) / se_pool
    p_value = 2 * stats.norm.sf(abs(z))
    return (z, p_value)


# ── Full experiment simulation ─────────────────────────────────────────────────

def run_simulated_experiment(
    baseline_rate: float,
    treatment_rate: float,
    n_per_arm: int,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Simulate a randomized experiment and compute all statistics.

    Parameters
    ----------
    baseline_rate  : control true conversion rate
    treatment_rate : treatment true conversion rate
    n_per_arm      : number of observations per arm
    alpha          : significance threshold
    seed           : random seed for reproducibility

    Returns
    -------
    dict with full experiment results (ALL SIMULATED).
    """
    # Validate inputs
    for name, val in [("baseline_rate", baseline_rate), ("treatment_rate", treatment_rate)]:
        if not (0 < val < 1):
            raise ValueError(f"{name} must be strictly between 0 and 1.")
    if n_per_arm < 2:
        raise ValueError("n_per_arm must be at least 2.")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be between 0 and 1.")

    rng = np.random.default_rng(seed)

    # Simulate conversions
    ctrl_conversions = int(rng.binomial(n_per_arm, baseline_rate))
    treat_conversions = int(rng.binomial(n_per_arm, treatment_rate))

    obs_ctrl_rate = ctrl_conversions / n_per_arm
    obs_treat_rate = treat_conversions / n_per_arm
    abs_diff = obs_treat_rate - obs_ctrl_rate
    rel_lift = (abs_diff / obs_ctrl_rate * 100) if obs_ctrl_rate > 0 else None

    z_stat, p_value = two_proportion_ztest(n_per_arm, ctrl_conversions, n_per_arm, treat_conversions)
    ci_low, ci_high = diff_proportion_ci(n_per_arm, ctrl_conversions, n_per_arm, treat_conversions)

    ctrl_ci = wilson_ci(ctrl_conversions, n_per_arm)
    treat_ci = wilson_ci(treat_conversions, n_per_arm)

    mde = abs(treatment_rate - baseline_rate)
    recommended_n = required_sample_size(baseline_rate, mde=max(mde, 0.001), alpha=alpha)

    significant = bool((not math.isnan(p_value)) and (p_value < alpha))

    # Interpretation
    if math.isnan(p_value):
        interpretation = "Insufficient data to compute a test statistic."
    elif significant:
        direction = "higher" if abs_diff > 0 else "lower"
        interpretation = (
            f"The observed difference is statistically significant (p={p_value:.4f} < {alpha}). "
            f"The treatment conversion rate is {direction} than control in this simulation. "
            f"Statistical significance does not guarantee commercial importance."
        )
    else:
        interpretation = (
            f"The observed difference is NOT statistically significant (p={p_value:.4f} ≥ {alpha}). "
            "This does not prove the variants are equivalent — the test may be underpowered. "
            f"Consider whether n={n_per_arm:,} per arm is sufficient for the target MDE."
        )

    return {
        "disclaimer": EXPERIMENT_DISCLAIMER,
        "inputs": {
            "baseline_rate":  baseline_rate,
            "treatment_rate": treatment_rate,
            "n_per_arm":      n_per_arm,
            "alpha":          alpha,
            "seed":           seed,
        },
        "simulated": {
            "ctrl_n":          n_per_arm,
            "ctrl_conversions": ctrl_conversions,
            "obs_ctrl_rate":   round(obs_ctrl_rate, 4),
            "ctrl_ci_low":     round(ctrl_ci[0], 4),
            "ctrl_ci_high":    round(ctrl_ci[1], 4),
            "treat_n":         n_per_arm,
            "treat_conversions": treat_conversions,
            "obs_treat_rate":  round(obs_treat_rate, 4),
            "treat_ci_low":    round(treat_ci[0], 4),
            "treat_ci_high":   round(treat_ci[1], 4),
        },
        "statistics": {
            "abs_diff_pp":     round(abs_diff * 100, 4),
            "rel_lift_pct":    round(rel_lift, 2) if rel_lift is not None else None,
            "ci_diff_low_pp":  round(ci_low * 100, 4),
            "ci_diff_high_pp": round(ci_high * 100, 4),
            "z_statistic":     round(z_stat, 4) if not math.isnan(z_stat) else None,
            "p_value":         round(p_value, 6) if not math.isnan(p_value) else None,
            "significant":     significant,
            "recommended_n_per_arm": recommended_n,
            "achieved_vs_recommended": (
                f"{n_per_arm:,} achieved vs {recommended_n:,} recommended"
            ),
        },
        "interpretation": interpretation,
    }
