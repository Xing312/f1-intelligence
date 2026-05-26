import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from src.pipeline.session_loader import load_session, COMPOUND_COLORS
from src.analysis.tire_analysis import (
    get_stints, get_all_degradation, compound_comparison, pit_window_estimate
)

st.set_page_config(page_title="Tire Strategy", page_icon="🔄", layout="wide")
st.title("🔄 Tire Strategy")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
session_code = st.session_state.get("session_code", "R")
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")


@st.cache_resource(show_spinner="Loading session data…")
def load(yr, rnd, sc):
    return load_session(yr, rnd, sc)


session = load(year, round_num, session_code)

# ── Stint Timeline (Gantt) ─────────────────────────────────────────────────────
st.subheader("Stint Timeline")
try:
    stints = get_stints(session)
    drivers_ordered = (
        session.results.sort_values("Position")["Abbreviation"].tolist()
    )

    fig_gantt = go.Figure()
    for driver in drivers_ordered:
        d_stints = stints[stints["Driver"] == driver]
        for _, row in d_stints.drop_duplicates("Stint").iterrows():
            stint_rows = d_stints[d_stints["Stint"] == row["Stint"]]
            start = int(stint_rows["LapNumber"].min())
            end = int(stint_rows["LapNumber"].max())
            compound = row["Compound"]
            color = COMPOUND_COLORS.get(compound, "#999")
            fig_gantt.add_trace(go.Bar(
                x=[end - start + 1], y=[driver],
                base=[start], orientation="h",
                marker_color=color,
                marker_line=dict(color="#0F0F0F", width=1),
                name=compound,
                showlegend=False,
                hovertemplate=f"{driver} · {compound}<br>Laps {start}–{end}<extra></extra>",
            ))

    # Legend traces
    for compound, color in COMPOUND_COLORS.items():
        fig_gantt.add_trace(go.Bar(x=[0], y=[""], orientation="h",
                                   marker_color=color, name=compound,
                                   showlegend=True))

    fig_gantt.update_layout(
        barmode="stack",
        xaxis_title="Lap",
        yaxis=dict(categoryorder="array", categoryarray=list(reversed(drivers_ordered))),
        paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
        height=max(300, len(drivers_ordered) * 22),
        margin=dict(t=10), legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_gantt, use_container_width=True)
except Exception as e:
    st.warning(f"Stint timeline unavailable: {e}")

st.divider()

# ── Degradation Analysis ───────────────────────────────────────────────────────
st.subheader("Tire Degradation")
try:
    all_deg = get_all_degradation(session)
    drivers = sorted(set(d["Driver"] for d in all_deg))
    sel_driver = st.selectbox("Driver", drivers)

    driver_deg = [d for d in all_deg if d["Driver"] == sel_driver]
    fig_deg = go.Figure()

    for stint in driver_deg:
        clean = stint["CleanLaps"]
        if clean.empty:
            continue
        compound = stint["Compound"]
        color = COMPOUND_COLORS.get(compound, "#999")

        fig_deg.add_trace(go.Scatter(
            x=clean["TyreLife"], y=clean["LapTimeSec"],
            mode="markers", name=f"Stint {stint['Stint']} · {compound}",
            marker=dict(color=color, size=7),
            hovertemplate="Tyre age: %{x}<br>Lap time: %{y:.3f}s<extra></extra>",
        ))

        if stint["Slope"] is not None:
            x_range = np.array([clean["TyreLife"].min(), clean["TyreLife"].max()])
            y_fit = stint["Intercept"] * x_range  # intercept + slope * x
            y_fit = stint["Intercept"] + stint["Slope"] * x_range
            fig_deg.add_trace(go.Scatter(
                x=x_range, y=y_fit,
                mode="lines", name=f"Trend (slope={stint['Slope']:+.3f}s/lap)",
                line=dict(color=color, dash="dash"),
            ))

    fig_deg.update_layout(
        xaxis_title="Tyre Age (laps)", yaxis_title="Lap Time (s)",
        paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
        height=380, margin=dict(t=10), legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_deg, use_container_width=True)

    # Pit window estimates
    if driver_deg:
        st.subheader("Pit Window Estimates")
        cols = st.columns(len(driver_deg))
        for i, stint in enumerate(driver_deg):
            with cols[i]:
                slope = stint["Slope"]
                window = pit_window_estimate(slope, 90) if slope else -1
                if window == -1:
                    st.metric(f"Stint {stint['Stint']} · {stint['Compound']}",
                              "Stable / no deg")
                else:
                    st.metric(f"Stint {stint['Stint']} · {stint['Compound']}",
                              f"~{window} laps",
                              help=f"Degradation slope: {slope:+.3f}s/lap")

except Exception as e:
    st.warning(f"Degradation analysis unavailable: {e}")

st.divider()

# ── Compound Comparison ────────────────────────────────────────────────────────
st.subheader("Compound Pace Comparison")
try:
    comp = compound_comparison(session)
    if not comp.empty:
        fig_comp = go.Figure(go.Bar(
            x=comp["Compound"], y=comp["avg_lap"],
            marker_color=comp["Color"].tolist(),
            error_y=dict(type="data", array=comp["std"].tolist()),
            hovertemplate="%{x}: %{y:.3f}s avg<extra></extra>",
        ))
        fig_comp.update_layout(
            xaxis_title="Compound", yaxis_title="Avg Clean Lap Time (s)",
            paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
            height=300, margin=dict(t=10),
        )
        st.plotly_chart(fig_comp, use_container_width=True)
        st.dataframe(comp[["Compound", "avg_lap", "std", "laps"]].rename(columns={
            "avg_lap": "Avg Lap (s)", "std": "Std Dev", "laps": "Sample Laps"
        }), use_container_width=True, hide_index=True)
except Exception as e:
    st.warning(f"Compound comparison unavailable: {e}")
