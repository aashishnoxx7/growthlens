"""
Visualization helpers for GrowthLens — Plotly-based charts with a consistent
design language: light theme, navy/charcoal text, accent blue #2563EB.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── Design tokens ─────────────────────────────────────────────────────────────
ACCENT = "#2563EB"       # primary accent blue
ACCENT2 = "#7C3AED"      # secondary accent purple
SUCCESS = "#059669"      # green
WARNING = "#D97706"      # amber
DANGER = "#DC2626"       # red
TEXT_DARK = "#1E293B"    # near-black
TEXT_MED = "#475569"     # medium grey
BG = "#F8FAFC"           # off-white background
BORDER = "#E2E8F0"       # subtle border

FONT_FAMILY = "Inter, system-ui, -apple-system, sans-serif"

LAYOUT_BASE = dict(
    font=dict(family=FONT_FAMILY, color=TEXT_DARK, size=13),
    plot_bgcolor=BG,
    paper_bgcolor="white",
    margin=dict(l=16, r=16, t=48, b=16),
    hoverlabel=dict(
        bgcolor="white",
        bordercolor=BORDER,
        font=dict(family=FONT_FAMILY, size=12),
    ),
)


def _base_layout(**kwargs) -> dict:
    layout = dict(**LAYOUT_BASE)
    layout.update(kwargs)
    return layout


# ── Daily trends ──────────────────────────────────────────────────────────────

def plot_daily_trends(daily_df: pd.DataFrame) -> go.Figure:
    """Line chart of daily events and purchases."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=daily_df["event_date"],
        y=daily_df["unique_users"],
        name="Unique Users",
        line=dict(color=ACCENT, width=2.5),
        hovertemplate="%{x}<br>Users: %{y:,}<extra></extra>",
    ))

    if "purchases" in daily_df.columns:
        fig.add_trace(go.Scatter(
            x=daily_df["event_date"],
            y=daily_df["purchases"],
            name="Purchases",
            line=dict(color=SUCCESS, width=2, dash="dash"),
            yaxis="y2",
            hovertemplate="%{x}<br>Purchases: %{y:,}<extra></extra>",
        ))

    fig.update_layout(
        **_base_layout(
            title=dict(text="Daily Traffic & Purchase Trends", font=dict(size=16, color=TEXT_DARK)),
            yaxis=dict(title="Unique Users", gridcolor=BORDER, zeroline=False),
            yaxis2=dict(title="Purchases", overlaying="y", side="right", gridcolor=BORDER, zeroline=False),
            legend=dict(orientation="h", y=-0.2, x=0),
            hovermode="x unified",
        )
    )
    return fig


# ── Funnel ────────────────────────────────────────────────────────────────────

def plot_funnel(funnel_df: pd.DataFrame) -> go.Figure:
    """Plotly funnel chart with stage labels and conversion rates."""
    colors = [ACCENT, "#3B82F6", "#60A5FA", SUCCESS]

    fig = go.Figure(go.Funnel(
        y=funnel_df["label"].tolist(),
        x=funnel_df["sessions"].tolist(),
        textposition="inside",
        textinfo="value+percent initial",
        opacity=0.92,
        marker=dict(color=colors[:len(funnel_df)], line=dict(width=0)),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Sessions: %{value:,}<br>"
            "% of first stage: %{percentInitial:.1%}<extra></extra>"
        ),
    ))

    fig.update_layout(**_base_layout(
        title=dict(text="Session-Based Conversion Funnel", font=dict(size=16, color=TEXT_DARK)),
    ))
    return fig


def plot_funnel_bars(funnel_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart for the funnel with step-to-step conversion."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=funnel_df["label"],
        x=funnel_df["sessions"],
        orientation="h",
        marker_color=ACCENT,
        text=funnel_df["sessions"].apply(lambda x: f"{x:,}"),
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>Sessions: %{x:,}<extra></extra>"
        ),
    ))

    fig.update_layout(**_base_layout(
        title=dict(text="Funnel Sessions by Stage", font=dict(size=16, color=TEXT_DARK)),
        xaxis=dict(title="Sessions", gridcolor=BORDER),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    ))
    return fig


# ── Retention heatmap ─────────────────────────────────────────────────────────

def plot_retention_heatmap(retention_df: pd.DataFrame) -> go.Figure:
    """Cohort retention heatmap."""
    if retention_df.empty:
        return go.Figure()

    z = retention_df.values.tolist()
    y_labels = [str(c)[:10] for c in retention_df.index]
    x_labels = [f"Week {c}" for c in retention_df.columns]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_labels,
        y=y_labels,
        colorscale=[
            [0.0, "#EFF6FF"],
            [0.3, "#93C5FD"],
            [0.6, "#3B82F6"],
            [1.0, "#1D4ED8"],
        ],
        zmin=0,
        zmax=100,
        text=[[f"{v:.0f}%" if v == v else "—" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate=(
            "Cohort: %{y}<br>%{x}<br>Retention: %{z:.1f}%<extra></extra>"
        ),
        showscale=True,
        colorbar=dict(title="Retention %", ticksuffix="%"),
    ))

    fig.update_layout(**_base_layout(
        title=dict(text="Weekly Cohort Retention Heatmap", font=dict(size=16, color=TEXT_DARK)),
        xaxis=dict(side="top"),
        margin=dict(l=120, r=16, t=80, b=16),
    ))
    return fig


# ── Acquisition matrix ────────────────────────────────────────────────────────

def plot_acquisition_matrix(acq_df: pd.DataFrame) -> go.Figure:
    """Bubble chart: volume vs conversion by source."""
    if acq_df.empty:
        return go.Figure()

    src_col = "traffic_source" if "traffic_source" in acq_df.columns else acq_df.columns[0]

    fig = px.scatter(
        acq_df[~acq_df.get("low_sample", pd.Series(False))],
        x="sessions",
        y="conversion_rate_pct",
        size="sessions",
        color=src_col,
        hover_name=src_col,
        hover_data={
            "sessions": ":,",
            "conversion_rate_pct": ":.2f",
            "sessions_purchase": ":,",
        },
        labels={
            "sessions": "Sessions",
            "conversion_rate_pct": "Conversion Rate (%)",
            src_col: "Source",
        },
        title="Acquisition: Volume vs Conversion Rate",
        color_discrete_sequence=px.colors.qualitative.Bold,
    )

    fig.update_layout(**_base_layout(
        xaxis=dict(title="Sessions", gridcolor=BORDER),
        yaxis=dict(title="Conversion Rate (%)", gridcolor=BORDER),
    ))
    return fig


# ── Device bar chart ──────────────────────────────────────────────────────────

def plot_device_breakdown(device_df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: sessions and conversion by device."""
    if device_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Sessions",
        x=device_df["device_category"],
        y=device_df["sessions"],
        marker_color=ACCENT,
        hovertemplate="<b>%{x}</b><br>Sessions: %{y:,}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Purchases",
        x=device_df["device_category"],
        y=device_df["sessions_purchase"],
        marker_color=SUCCESS,
        hovertemplate="<b>%{x}</b><br>Purchases: %{y:,}<extra></extra>",
    ))

    fig.update_layout(**_base_layout(
        title=dict(text="Sessions & Purchases by Device", font=dict(size=16, color=TEXT_DARK)),
        barmode="group",
        xaxis=dict(title="Device"),
        yaxis=dict(title="Sessions", gridcolor=BORDER),
        legend=dict(orientation="h", y=-0.2),
    ))
    return fig


# ── Experiment results ────────────────────────────────────────────────────────

def plot_experiment_results(result: dict) -> go.Figure:
    """Side-by-side bar chart comparing control and treatment conversion rates."""
    sim = result.get("simulated", {})
    ctrl_rate = sim.get("obs_ctrl_rate", 0) * 100
    treat_rate = sim.get("obs_treat_rate", 0) * 100
    ctrl_ci_low = sim.get("ctrl_ci_low", 0) * 100
    ctrl_ci_high = sim.get("ctrl_ci_high", 0) * 100
    treat_ci_low = sim.get("treat_ci_low", 0) * 100
    treat_ci_high = sim.get("treat_ci_high", 0) * 100

    fig = go.Figure()
    for label, rate, ci_low, ci_high, color in [
        ("Control", ctrl_rate, ctrl_ci_low, ctrl_ci_high, TEXT_MED),
        ("Treatment", treat_rate, treat_ci_low, treat_ci_high, ACCENT),
    ]:
        fig.add_trace(go.Bar(
            name=label,
            x=[label],
            y=[rate],
            error_y=dict(
                type="data",
                symmetric=False,
                array=[ci_high - rate],
                arrayminus=[rate - ci_low],
                visible=True,
            ),
            marker_color=color,
            text=[f"{rate:.2f}%"],
            textposition="outside",
            hovertemplate=(
                f"<b>{label}</b><br>Conversion: {rate:.2f}%<br>"
                f"95% CI: [{ci_low:.2f}%, {ci_high:.2f}%]<extra></extra>"
            ),
        ))

    fig.update_layout(**_base_layout(
        title=dict(text="Simulated Experiment: Conversion Rates with 95% CI", font=dict(size=16, color=TEXT_DARK)),
        yaxis=dict(title="Conversion Rate (%)", gridcolor=BORDER),
        showlegend=True,
        legend=dict(orientation="h", y=-0.2),
    ))
    return fig


# ── KPI card helper (returns HTML for st.markdown) ────────────────────────────

def kpi_card_html(
    label: str,
    value: str,
    sub: str = "",
    color: str = ACCENT,
) -> str:
    return f"""
<div style="
    background:#fff;
    border:1px solid {BORDER};
    border-top:3px solid {color};
    border-radius:8px;
    padding:16px 20px;
    font-family:{FONT_FAMILY};
">
  <div style="font-size:12px;color:{TEXT_MED};text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">{label}</div>
  <div style="font-size:28px;font-weight:700;color:{TEXT_DARK}">{value}</div>
  <div style="font-size:12px;color:{TEXT_MED};margin-top:4px">{sub}</div>
</div>
"""
