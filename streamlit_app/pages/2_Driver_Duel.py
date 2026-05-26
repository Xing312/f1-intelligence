import sys
import importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from src.pipeline.db import get_drivers, get_sc_laps

import src.analysis.lap_analysis as _la
importlib.reload(_la)
from src.analysis.lap_analysis import (
    get_lap_comparison, get_sector_delta_pivot,
    get_consistency_score, auto_summary,
)


@st.cache_data(show_spinner=False)
def _load_driver_telemetry(yr: int, rnd: int, drv_a: str, drv_b: str):
    from src.pipeline.db import get_telemetry
    return get_telemetry(yr, rnd, drv_a), get_telemetry(yr, rnd, drv_b)

st.set_page_config(page_title="Driver Duel", page_icon="⚔️", layout="wide")
st.title("⚔️ Driver Duel")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")

drivers = get_drivers(year, round_num)
if len(drivers) < 2:
    st.warning("Not enough driver data available for this race.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    driver_a = st.selectbox("Driver A", drivers, index=0)
with col2:
    driver_b = st.selectbox("Driver B", drivers, index=min(1, len(drivers) - 1))

if driver_a == driver_b:
    st.warning("Select two different drivers.")
    st.stop()

# ── Lap Time Comparison ────────────────────────────────────────────────────────
st.subheader("Lap Time Comparison")
try:
    laps = get_lap_comparison(year, round_num, driver_a, driver_b)
    sc_laps = get_sc_laps(year, round_num)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=laps["LapNumber"], y=laps[driver_a],
        name=driver_a, mode="lines+markers",
        line=dict(color="#E8002D"), marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=laps["LapNumber"], y=laps[driver_b],
        name=driver_b, mode="lines+markers",
        line=dict(color="#4FC3F7"), marker=dict(size=4),
    ))
    for lap_n in sc_laps:
        fig.add_vrect(x0=lap_n - 0.5, x1=lap_n + 0.5,
                      fillcolor="rgba(255,255,0,0.1)", line_width=0)

    fig.update_layout(
        xaxis_title="Lap", yaxis_title="Lap Time (s)",
        paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
        legend=dict(orientation="h"), height=320, margin=dict(t=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Yellow bands = Safety Car laps")
except Exception as e:
    st.warning(f"Lap comparison unavailable: {e}")

st.divider()

# ── Sector Delta Heatmap ───────────────────────────────────────────────────────
st.subheader(f"Sector Delta — positive = {driver_a} faster")
try:
    pivot = get_sector_delta_pivot(year, round_num, driver_a, driver_b)
    if not pivot.empty:
        fig_heat = px.imshow(
            pivot.T,
            color_continuous_scale="RdBu",
            color_continuous_midpoint=0,
            aspect="auto",
            labels=dict(color="Delta (s)"),
        )
        fig_heat.update_layout(
            xaxis_title="Lap", yaxis_title="Sector",
            paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F",
            font_color="#FFF", height=220, margin=dict(t=10),
            coloraxis_colorbar=dict(title="Δ (s)", tickformat=".2f"),
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("No sector data available.")
except Exception as e:
    st.warning(f"Sector delta unavailable: {e}")

st.divider()

# ── Consistency Scorecards ─────────────────────────────────────────────────────
st.subheader("Consistency")
c1, c2 = st.columns(2)
for driver, col in [(driver_a, c1), (driver_b, c2)]:
    try:
        score = get_consistency_score(year, round_num, driver)
        with col:
            st.metric(f"{driver} — Mean Lap", f"{score['mean']:.3f}s" if score["mean"] else "—")
            st.metric("Std Dev", f"±{score['std']:.3f}s" if score["std"] else "—")
            st.metric("Clean Laps", score["n_laps"])
    except Exception:
        col.metric(driver, "N/A")

st.divider()

# ── Auto Summary ───────────────────────────────────────────────────────────────
st.subheader("Analysis Summary")
try:
    summary = auto_summary(year, round_num, driver_a, driver_b)
    st.markdown(summary)
except Exception as e:
    st.info(f"Summary unavailable: {e}")

st.divider()

# ── Telemetry & Track Delta ────────────────────────────────────────────────────
st.subheader("Telemetry & Track Delta")
if True:
    try:
        import src.analysis.track_map as _tm
        importlib.reload(_tm)
        from plotly.subplots import make_subplots

        tel_a, tel_b = _load_driver_telemetry(year, round_num, driver_a, driver_b)

        channels = ["Speed", "Throttle", "Brake"]
        fig_tel = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                subplot_titles=channels, vertical_spacing=0.06)
        for i, ch in enumerate(channels, 1):
            if ch in tel_a.columns:
                fig_tel.add_trace(go.Scatter(
                    x=tel_a["Distance"], y=tel_a[ch],
                    name=driver_a, line=dict(color="#E8002D"),
                    showlegend=(i == 1),
                ), row=i, col=1)
            if ch in tel_b.columns:
                fig_tel.add_trace(go.Scatter(
                    x=tel_b["Distance"], y=tel_b[ch],
                    name=driver_b, line=dict(color="#4FC3F7"),
                    showlegend=(i == 1),
                ), row=i, col=1)

        fig_tel.update_layout(
            paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
            height=500, margin=dict(t=30), legend=dict(orientation="h"),
        )
        fig_tel.update_xaxes(title_text="Distance (m)", row=3, col=1)
        st.plotly_chart(fig_tel, use_container_width=True)

        st.subheader("Track Delta Map")
        fig_delta = _tm.build_delta_map(tel_a, tel_b, driver_a, driver_b)
        st.plotly_chart(fig_delta, use_container_width=True)

    except Exception as e:
        st.warning(f"Telemetry unavailable: {e}")
