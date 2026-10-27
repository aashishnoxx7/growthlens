"""
GrowthLens — Experiment Lab
A/B test simulator using statistical methods. ALL results are SIMULATED.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st

from growthlens.experimentation import EXPERIMENT_DISCLAIMER, required_sample_size, run_simulated_experiment
from growthlens.visualization import plot_experiment_results

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Experiment Lab — GrowthLens", layout="wide")

st.title("🧪 Experiment Lab")
st.caption("Design and simulate A/B tests. Configure parameters and run a simulation.")

# ── Header overview ───────────────────────────────────────────────────────────
st.markdown(
    """
<div style="
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #2563EB;
    border-radius: 6px;
    padding: 12px 18px;
    margin-bottom: 20px;
">
  <div style="font-weight: 600; color: #1E293B; font-size: 14px;">
    Statistical Hypothesis & Sample Size Modeling
  </div>
  <div style="color: #64748B; font-size: 13px; margin-top: 2px;">
    Evaluate required sample sizes, minimum detectable effect (MDE), statistical power (1 - β), and significance thresholds (α) before launching experimentation variants.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Sidebar: Experiment inputs ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚗️ Experiment Parameters")

    baseline_rate = st.slider(
        "Baseline Conversion Rate",
        min_value=0.01,
        max_value=0.50,
        value=0.05,
        step=0.01,
        format="%.2f",
        key="exp_baseline",
        help="The control arm's true conversion rate (e.g. 0.05 = 5%).",
    )

    mde = st.number_input(
        "Minimum Detectable Effect (absolute pp)",
        min_value=0.001,
        max_value=0.20,
        value=0.02,
        step=0.001,
        format="%.3f",
        key="exp_mde",
        help="The smallest absolute difference you want to reliably detect (e.g. 0.02 = 2 pp).",
    )

    n_per_arm = st.number_input(
        "Observations per Arm",
        min_value=100,
        max_value=1_000_000,
        value=10_000,
        step=100,
        key="exp_n",
        help="Number of users assigned to each arm (control and treatment).",
    )

    alpha = st.slider(
        "Significance Level (α)",
        min_value=0.01,
        max_value=0.20,
        value=0.05,
        step=0.01,
        format="%.2f",
        key="exp_alpha",
        help="Type I error rate. Lower α reduces false positives but requires larger samples.",
    )

    power = st.slider(
        "Statistical Power (1 − β)",
        min_value=0.50,
        max_value=0.99,
        value=0.80,
        step=0.01,
        format="%.2f",
        key="exp_power",
        help="Probability of detecting a true effect of size MDE. Higher power requires larger samples.",
    )

    seed = st.number_input(
        "Random Seed",
        min_value=0,
        max_value=999_999,
        value=42,
        step=1,
        key="exp_seed",
        help="Changing the seed produces different random outcomes at identical parameters.",
    )

    run_btn = st.button("▶️ Run Simulation", type="primary", use_container_width=True)

# ── Recommended sample size ───────────────────────────────────────────────────
st.subheader("📐 Sample Size Planning")

try:
    rec_n = required_sample_size(baseline_rate, mde=mde, alpha=alpha, power=power)
    col_rec1, col_rec2, col_rec3 = st.columns(3)
    with col_rec1:
        st.metric("Recommended N per Arm", f"{rec_n:,}", help="Minimum per-arm size to detect MDE at given α and power.")
    with col_rec2:
        st.metric("Your N per Arm", f"{int(n_per_arm):,}")
    with col_rec3:
        if n_per_arm >= rec_n:
            st.metric("Status", "✅ Adequately Powered", delta=f"+{int(n_per_arm - rec_n):,} above minimum")
        else:
            deficit = rec_n - int(n_per_arm)
            st.metric("Status", "⚠️ Underpowered", delta=f"-{deficit:,} below recommended", delta_color="inverse")

    if n_per_arm < rec_n:
        st.warning(
            f"Your current N ({int(n_per_arm):,}) is below the recommended {rec_n:,} per arm. "
            f"The test may be underpowered to detect a {mde*100:.1f} pp effect at "
            f"α={alpha} and power={power:.0%}."
        )
except Exception as e:
    st.error(f"Sample size calculation failed: {e}")
    rec_n = None

st.markdown("---")

# ── Run simulation ────────────────────────────────────────────────────────────
if run_btn:
    treatment_rate = baseline_rate + mde

    # Clamp treatment rate below 1
    if treatment_rate >= 1.0:
        st.error(f"Baseline ({baseline_rate:.2f}) + MDE ({mde:.3f}) ≥ 1.0. Please reduce baseline or MDE.")
        st.stop()

    st.subheader("🔬 Simulation Results")
    st.markdown(
        '<div style="background:#FFF7ED;border-left:4px solid #F59E0B;padding:10px 16px;'
        'border-radius:4px;font-size:12px;color:#92400E;margin-bottom:16px;">'
        f'<strong>Simulated parameters:</strong> baseline={baseline_rate:.3f}, '
        f'treatment={treatment_rate:.3f}, n={int(n_per_arm):,}/arm, α={alpha}, seed={seed}'
        '</div>',
        unsafe_allow_html=True,
    )

    try:
        result = run_simulated_experiment(
            baseline_rate=baseline_rate,
            treatment_rate=treatment_rate,
            n_per_arm=int(n_per_arm),
            alpha=alpha,
            seed=int(seed),
        )
    except Exception as e:
        st.error(f"Simulation failed: {e}")
        st.stop()

    sim = result.get("simulated", {})
    stats = result.get("statistics", {})

    # Results metrics row
    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
    with col_r1:
        ctrl_rate_pct = sim.get("obs_ctrl_rate", 0) * 100
        st.metric("Control Rate", f"{ctrl_rate_pct:.2f}%", help="Observed conversion rate in control arm.")
    with col_r2:
        treat_rate_pct = sim.get("obs_treat_rate", 0) * 100
        st.metric("Treatment Rate", f"{treat_rate_pct:.2f}%", help="Observed conversion rate in treatment arm.")
    with col_r3:
        abs_diff = stats.get("abs_diff_pp", 0)
        st.metric("Abs. Difference", f"{abs_diff:+.3f} pp", help="Treatment minus control (percentage points).")
    with col_r4:
        p_val = stats.get("p_value")
        p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
        st.metric("p-value", p_str)
    with col_r5:
        significant = stats.get("significant", False)
        st.metric(
            "Significant?",
            "✅ Yes" if significant else "❌ No",
            help=f"At α = {alpha}",
        )

    st.markdown("")

    # Plot
    fig = plot_experiment_results(result)
    st.plotly_chart(fig, use_container_width=True)

    # CI explanation
    ci_low = stats.get("ci_diff_low_pp", 0)
    ci_high = stats.get("ci_diff_high_pp", 0)
    st.markdown(
        f"**95% Confidence Interval for the Difference (Treatment − Control)**: "
        f"[{ci_low:+.3f} pp, {ci_high:+.3f} pp]"
    )
    st.caption(
        "The confidence interval is computed using the normal approximation for the difference in proportions. "
        "If the interval excludes zero, the result is statistically significant at the chosen α."
    )

    # Interpretation
    st.markdown("#### 📝 Interpretation")
    interp = result.get("interpretation", "")
    if significant:
        st.success(interp)
    else:
        st.warning(interp)

    # Rel lift
    rel_lift = stats.get("rel_lift_pct")
    if rel_lift is not None:
        st.caption(f"Relative lift: {rel_lift:+.2f}% (treatment rate relative to control)")

    st.markdown("---")

    # Achieved vs recommended
    achieved_vs_rec = stats.get("achieved_vs_recommended", "")
    if achieved_vs_rec:
        st.caption(f"Sample size: {achieved_vs_rec}")

else:
    st.info("Configure parameters in the sidebar and click **▶️ Run Simulation** to generate results.")

# ── Statistical assumptions ───────────────────────────────────────────────────
with st.expander("📖 Statistical Methods & Assumptions"):
    st.markdown(f"""
**Test Type** — Two-sided two-proportion z-test. The null hypothesis is that the control
and treatment conversion rates are equal. Two-sided testing is recommended unless there
is a strong a-priori directional hypothesis.

**Pooled Standard Error** — Under H₀, a pooled proportion is used to estimate the
standard error: `SE = sqrt(p_pool * (1 - p_pool) * (1/n_ctrl + 1/n_treat))`.

**Wilson Score Confidence Intervals** — Per-arm CIs use the Wilson score method,
which is more accurate near 0 and 1 than the normal approximation. The difference CI
uses the normal approximation.

**Sample Size Formula** — `n = (z_α/2 + z_β)² × (p₁(1-p₁) + p₂(1-p₂)) / δ²`  
where p₁ = baseline, p₂ = baseline + MDE, δ = MDE.

**Type I Error (α = {alpha:.2f})** — The probability of incorrectly rejecting H₀ when it is true
(false positive rate). Setting α = {alpha:.2f} means ≈{alpha*100:.0f}% chance of a false significant result
in a single test.

**Type II Error (1 − power = {1-power:.2f})** — The probability of failing to detect a true effect
of size MDE (false negative rate). The default power of {power:.0%} means ≈{(1-power)*100:.0f}% chance of
missing a real effect.

**Random Seed** — Results are reproducible at a fixed seed. Changing the seed
resamples the simulated data, potentially changing significance. This highlights
that individual experiment outcomes have inherent randomness.

**Limitations**:
- Simulated data follows a binomial distribution. Real-world data may violate assumptions.
- This tool does not account for multiple testing corrections (FWER/FDR).
- Novelty effects, learning curves, and seasonal effects are not modeled.
- All results shown here are **not real A/B test outcomes**.
""")
