import sys
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import plotly.graph_objects as go
from src.pipeline.db import get_drivers, get_race_control
from src.analysis.anomaly import flag_laps, get_anomaly_summary, FLAG_COLORS, FLAG_LABELS

st.set_page_config(page_title="Anomaly Detection", page_icon="🔍", layout="wide")
st.title("🔍 Anomaly Detection")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")

drivers = get_drivers(year, round_num)
if not drivers:
    st.warning("No driver data available for this race.")
    st.stop()

driver = st.selectbox("Driver", drivers)

# ── Lap Timeline ───────────────────────────────────────────────────────────────
st.subheader("Lap Timeline")
try:
    flagged = flag_laps(year, round_num, driver)

    fig = go.Figure()
    for flag_type, label in FLAG_LABELS.items():
        subset = flagged[flagged["Flag"] == flag_type]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["LapNumber"], y=subset["LapTimeSec"],
            mode="markers",
            marker=dict(
                color=FLAG_COLORS[flag_type], size=9,
                line=dict(color="#0F0F0F", width=1),
            ),
            name=label,
            hovertemplate=(
                "Lap %{x}<br>"
                "Time: %{y:.3f}s<br>"
                f"Type: {label}<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis_title="Lap", yaxis_title="Lap Time (s)",
        paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
        legend=dict(orientation="h"), height=360, margin=dict(t=10),
    )
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"Lap timeline unavailable: {e}")
    flagged = None

st.divider()

# ── Anomaly Summary Table ──────────────────────────────────────────────────────
st.subheader("Flagged Laps")
try:
    if flagged is not None:
        summary = get_anomaly_summary(flagged)
        if summary.empty:
            st.success("No anomalies detected for this driver.")
        else:
            summary["LapTimeSec"] = summary["LapTimeSec"].apply(
                lambda x: f"{x:.3f}s" if pd.notna(x) else "—"
            )
            st.dataframe(
                summary.rename(columns={
                    "LapNumber": "Lap", "LapTimeSec": "Lap Time",
                    "FlagLabel": "Type", "TyreLife": "Tyre Age",
                }),
                use_container_width=True, hide_index=True,
            )
except Exception as e:
    st.warning(f"Anomaly summary unavailable: {e}")

st.divider()

# ── Race Control Context ───────────────────────────────────────────────────────
st.subheader("Race Control Events")
try:
    rc = get_race_control(year, round_num)
    if rc.empty:
        st.info("No race control data available.")
    else:
        notable = rc[rc["Message"].str.contains(
            "SAFETY CAR|VIRTUAL|RED FLAG|YELLOW|BLUE|DRS", na=False, case=False
        )].copy()

        def infer_flag(row):
            if pd.notna(row.get("Flag")) and str(row["Flag"]) not in ("None", "", "nan"):
                return row["Flag"]
            msg = str(row["Message"]).upper()
            if "DRS ENABLED" in msg:
                return "DRSON"
            if "DRS DISABLED" in msg:
                return "DRSOFF"
            if "SAFETY CAR" in msg:
                return "SAFETY CAR"
            if "VIRTUAL" in msg:
                return "VSC"
            if "RED FLAG" in msg:
                return "RED"
            if "YELLOW" in msg:
                return "YELLOW"
            return "—"

        notable["Flag"] = notable.apply(infer_flag, axis=1)
        if notable.empty:
            st.info("No notable events.")
        else:
            st.dataframe(
                notable[["Lap", "Flag", "Message"]],
                use_container_width=True, hide_index=True,
            )
except Exception as e:
    st.warning(f"Race control unavailable: {e}")
