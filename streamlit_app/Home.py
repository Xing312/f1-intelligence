import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import fastf1

st.set_page_config(
    page_title="F1 Race Intelligence Hub",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏎️ F1 Race Intelligence Hub")
st.markdown(
    "Real-time F1 race analytics — lap telemetry, tire strategy, anomaly detection, and AI race engineering."
)

# ── Sidebar: Global Session Selector ──────────────────────────────────────────
with st.sidebar:
    st.header("Session")
    year = st.selectbox("Season", [2024, 2023, 2022], key="year")

    @st.cache_data(show_spinner=False)
    def get_schedule(yr):
        schedule = fastf1.get_event_schedule(yr, include_testing=False)
        return schedule[["RoundNumber", "EventName", "Location", "Country"]].copy()

    schedule = get_schedule(year)
    round_options = {
        f"R{int(row.RoundNumber):02d} · {row.EventName}": int(row.RoundNumber)
        for _, row in schedule.iterrows()
    }
    round_label = st.selectbox("Race", list(round_options.keys()), key="round_label")
    round_num = round_options[round_label]

    session_type = st.radio("Session", ["Race", "Qualifying"], key="session_type")
    session_code = "R" if session_type == "Race" else "Q"

    st.session_state["round_num"] = round_num
    st.session_state["session_code"] = session_code
    st.session_state["event_name"] = schedule[schedule["RoundNumber"] == round_num]["EventName"].iloc[0]

    st.divider()
    st.caption("Navigate using the pages above ↑")

# ── Landing content ────────────────────────────────────────────────────────────
event_name = st.session_state.get("event_name", "")
row = schedule[schedule["RoundNumber"] == round_num].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Event", event_name)
col2.metric("Circuit", row["Location"])
col3.metric("Session", session_type)

st.divider()
st.markdown("""
| Page | What you'll find |
|---|---|
| **Overview** | Race results, key stats, weather timeline, track speed map |
| **Driver Duel** | Lap-by-lap comparison, sector delta heatmap, telemetry overlay, track delta map |
| **Tire Strategy** | Stint timeline, degradation regression, compound pace comparison |
| **Anomaly Detection** | Lap flagging by z-score and race control events |
| **AI Race Engineer** | Ask questions about this race — answers grounded in telemetry data |
""")
