import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from src.pipeline.db import available_years, get_schedule

st.set_page_config(
    page_title="F1 Race Intelligence Hub",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏎️ F1 Race Intelligence Hub")
st.markdown(
    "F1 race analytics — lap data, tire strategy, anomaly detection, and AI race engineering."
)

# ── Sidebar: Global Session Selector ──────────────────────────────────────────
with st.sidebar:
    st.header("Session")

    years = available_years()
    if not years:
        st.error("No data found in database. Run fetch_data.py first.")
        st.stop()

    year = st.selectbox("Season", years, key="year")

    @st.cache_data(show_spinner=False)
    def _schedule(yr):
        return get_schedule(yr)

    schedule = _schedule(year)

    if schedule.empty:
        st.error(f"No races found for {year}.")
        st.stop()

    round_options = {
        f"R{int(row.Round):02d} · {row.EventName}": int(row.Round)
        for _, row in schedule.iterrows()
    }
    round_label = st.selectbox("Race", list(round_options.keys()), key="round_label")
    round_num = round_options[round_label]

    session_type = st.radio("Session", ["Race", "Qualifying"], key="session_type")
    session_code = "R" if session_type == "Race" else "Q"

    st.session_state["round_num"] = round_num
    st.session_state["session_code"] = session_code
    event_row = schedule[schedule["Round"] == round_num]
    st.session_state["event_name"] = event_row["EventName"].iloc[0] if not event_row.empty else ""

    st.divider()
    st.caption("Navigate using the pages above ↑")

# ── Landing content ────────────────────────────────────────────────────────────
event_name = st.session_state.get("event_name", "")
row = schedule[schedule["Round"] == round_num].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Event", event_name)
col2.metric("Circuit", row["Circuit"])
col3.metric("Session", session_type)

st.divider()
st.markdown("""
| Page | What you'll find |
|---|---|
| **Overview** | Race results, key stats, weather timeline, race control events |
| **Driver Duel** | Lap-by-lap comparison, sector delta heatmap, consistency scores |
| **Tire Strategy** | Stint timeline, degradation regression, compound pace comparison |
| **Anomaly Detection** | Lap flagging by z-score and race control events |
| **AI Race Engineer** | Ask questions about this race — answers grounded in race data |
""")
