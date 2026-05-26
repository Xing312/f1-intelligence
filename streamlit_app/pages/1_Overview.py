import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.pipeline.db import get_results, get_weather, get_race_control, fastest_lap

st.set_page_config(page_title="Overview", page_icon="🏁", layout="wide")
st.title("🏁 Race Overview")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")

# ── Race Results ───────────────────────────────────────────────────────────────
st.subheader("Results")
try:
    results = get_results(year, round_num)
    results = results[results["Position"].notna()].copy()
    results["_pos"] = pd.to_numeric(results["Position"], errors="coerce")
    results = results.sort_values("_pos")
    results["GridPosition"] = pd.to_numeric(results["GridPosition"], errors="coerce")
    results["Gained"] = (results["GridPosition"] - results["_pos"]).apply(
        lambda x: int(x) if pd.notna(x) else None
    )

    def style_results(df):
        medal = {
            1: "background-color:#FFD700;color:#000",
            2: "background-color:#C0C0C0;color:#000",
            3: "background-color:#CD7F32;color:#000",
        }
        def row_style(row):
            return [medal.get(row["_pos"], "")] * len(row)
        return df.style.apply(row_style, axis=1)

    display_cols = ["_pos", "Abbreviation", "FullName", "TeamName", "GridPosition", "Gained", "Points", "Status"]
    display = results[display_cols].rename(columns={"_pos": "Position"})
    st.dataframe(style_results(display), use_container_width=True, hide_index=True)
except Exception as e:
    st.warning(f"Results unavailable: {e}")

# ── Key Metrics ────────────────────────────────────────────────────────────────
st.subheader("Key Stats")
c1, c2, c3 = st.columns(3)

try:
    fl = fastest_lap(year, round_num)
    if fl is not None:
        t = fl["LapTimeSec"]
        m, s = divmod(t, 60)
        c1.metric("Fastest Lap", f"{fl['Driver']}  {int(m)}:{s:06.3f}")
    else:
        c1.metric("Fastest Lap", "—")
except Exception:
    c1.metric("Fastest Lap", "—")

try:
    results = get_results(year, round_num)
    results["_pos"] = pd.to_numeric(results["Position"], errors="coerce")
    results["GridPosition"] = pd.to_numeric(results["GridPosition"], errors="coerce")
    results["Gained"] = results["GridPosition"] - results["_pos"]
    gained_df = results.dropna(subset=["Gained"])
    if not gained_df.empty:
        mg = gained_df.sort_values("Gained", ascending=False).iloc[0]
        val = int(mg["Gained"])
        c2.metric("Most Positions Gained", f"{mg['Abbreviation']}  {'+' if val >= 0 else ''}{val}")
    else:
        c2.metric("Most Positions Gained", "—")

    sorted_r = results.sort_values("_pos")
    winner = sorted_r.iloc[0]
    pole_df = results[results["GridPosition"] == 1]
    if not pole_df.empty:
        pole = pole_df.iloc[0]
        c3.metric("Pole → Winner", f"{pole['Abbreviation']} → {winner['Abbreviation']}")
    else:
        c3.metric("Winner", winner["Abbreviation"])
except Exception:
    c2.metric("Most Positions Gained", "—")
    c3.metric("Winner", "—")

st.divider()

# ── Weather + Race Control ─────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Weather Timeline")
    try:
        weather = get_weather(year, round_num)
        if not weather.empty:
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(
                x=weather["TimeMin"], y=weather["AirTemp"],
                name="Air Temp (°C)", line=dict(color="#E8002D"),
            ))
            fig_w.add_trace(go.Scatter(
                x=weather["TimeMin"], y=weather["TrackTemp"],
                name="Track Temp (°C)", line=dict(color="#FF8C00"),
            ))
            if weather["Rainfall"].any():
                fig_w.add_trace(go.Bar(
                    x=weather["TimeMin"],
                    y=weather["Rainfall"].astype(float) * 5,
                    name="Rain", marker_color="#4FC3F7", opacity=0.4,
                ))
            fig_w.update_layout(
                xaxis_title="Time (min)", yaxis_title="°C",
                paper_bgcolor="#0F0F0F", plot_bgcolor="#0F0F0F", font_color="#FFF",
                legend=dict(orientation="h"), height=300, margin=dict(t=10, b=10),
            )
            st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.info("No weather data available.")
    except Exception as e:
        st.info(f"Weather data unavailable: {e}")

with col_right:
    st.subheader("Race Control Events")
    try:
        rc = get_race_control(year, round_num)
        if rc.empty:
            st.info("No race control data available.")
        else:
            notable = rc[rc["Message"].str.contains(
                "SAFETY CAR|VIRTUAL|RED FLAG|DRS|YELLOW|BLUE", na=False, case=False
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
            if not notable.empty:
                st.dataframe(
                    notable[["Lap", "Flag", "Message"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("No notable race control events.")
    except Exception as e:
        st.info(f"Race control data unavailable: {e}")

st.divider()

# ── Circuit Map (telemetry — on demand) ───────────────────────────────────────
st.subheader("Circuit Map")
st.caption("Track maps require downloading telemetry data from the F1 API (~30s).")

if st.button("Load Circuit Map"):
    st.session_state["load_overview_map"] = True

if st.session_state.get("load_overview_map"):
    with st.spinner("Loading telemetry…"):
        try:
            from src.pipeline.session_loader import load_session, get_fastest_lap as _fl
            from src.analysis.track_map import build_track_figure

            @st.cache_resource(show_spinner=False)
            def _load_session(yr, rnd):
                return load_session(yr, rnd, "R")

            session = _load_session(year, round_num)
            fl_driver = session.laps.pick_fastest()["Driver"]
            fl = _fl(session, fl_driver)

            channel = st.radio(
                "Color channel", ["Speed", "Throttle", "nGear", "Brake"],
                horizontal=True, key="overview_channel",
            )
            fig_map = build_track_figure(fl, channel)
            st.plotly_chart(fig_map, use_container_width=True)
        except Exception as e:
            st.warning(f"Circuit map unavailable: {e}")
