import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from src.pipeline.session_loader import load_session, get_race_control, get_weather, get_fastest_lap
from src.analysis.track_map import build_track_figure

st.set_page_config(page_title="Overview", page_icon="🏁", layout="wide")
st.title("🏁 Race Overview")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
session_code = st.session_state.get("session_code", "R")
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year} · {'Race' if session_code=='R' else 'Qualifying'}")


@st.cache_resource(show_spinner="Loading session data…")
def load(yr, rnd, sc):
    return load_session(yr, rnd, sc)


session = load(year, round_num, session_code)

# ── Circuit Map (top of page) ──────────────────────────────────────────────────
st.subheader("Circuit Map")
try:
    # Use the overall fastest lap driver for the circuit outline
    fl_driver = session.laps.pick_fastest()["Driver"]
    fl = get_fastest_lap(session, fl_driver)

    col_map, col_info = st.columns([2, 1])
    with col_map:
        channel = st.radio(
            "Color channel",
            ["Speed", "Throttle", "nGear", "Brake"],
            horizontal=True,
            key="overview_channel",
        )
        fig_map = build_track_figure(fl, channel)
        # Add corner annotations if available
        try:
            circuit_info = session.get_circuit_info()
            corners = circuit_info.corners
            tel = fl.get_telemetry().add_distance()
            pos = fl.get_pos_data()
            if not corners.empty and "X" in pos.columns:
                import numpy as np
                # Map corner distance to X/Y via interpolation
                dist_arr = tel["Distance"].values
                x_arr = tel["X"].values if "X" in tel.columns else pos["X"].values
                y_arr = tel["Y"].values if "Y" in tel.columns else pos["Y"].values
                for _, corner in corners.iterrows():
                    cx = float(np.interp(corner["Distance"], dist_arr, x_arr))
                    cy = float(np.interp(corner["Distance"], dist_arr, y_arr))
                    fig_map.add_annotation(
                        x=cx, y=cy,
                        text=f"T{int(corner['Number'])}",
                        showarrow=False,
                        font=dict(color="white", size=9),
                        bgcolor="rgba(0,0,0,0.5)",
                    )
        except Exception:
            pass
        st.plotly_chart(fig_map, use_container_width=True)

    with col_info:
        st.markdown("**Circuit Info**")
        try:
            ci = session.get_circuit_info()
            st.metric("Track Length", f"{ci.track_length / 1000:.3f} km")
        except Exception:
            pass
        event_row = session.event
        st.metric("Location", event_row.get("Location", "—"))
        st.metric("Country", event_row.get("Country", "—"))
        st.metric("Date", str(event_row.get("EventDate", "—"))[:10])
        try:
            w = get_weather(session)
            if not w.empty:
                st.metric("Air Temp (avg)", f"{w['AirTemp'].mean():.1f} °C")
                st.metric("Track Temp (avg)", f"{w['TrackTemp'].mean():.1f} °C")
                rain = "Yes 🌧️" if w["Rainfall"].any() else "No ☀️"
                st.metric("Rain", rain)
        except Exception:
            pass
except Exception as e:
    st.warning(f"Circuit map unavailable: {e}")

st.divider()

# ── Race Results ───────────────────────────────────────────────────────────────
st.subheader("Results")
results = session.results[
    ["Position", "Abbreviation", "FullName", "TeamName", "GridPosition", "Points", "Status"]
].copy()
results = results[results["Position"].notna()].sort_values("Position")
results["Position"] = results["Position"].astype(int)
results["GridPosition"] = pd.to_numeric(results["GridPosition"], errors="coerce")
results["Gained"] = (results["GridPosition"] - results["Position"]).where(
    results["GridPosition"].notna()
).apply(lambda x: int(x) if pd.notna(x) else None)


def style_results(df):
    medal = {1: "background-color:#FFD700;color:#000",
             2: "background-color:#C0C0C0;color:#000",
             3: "background-color:#CD7F32;color:#000"}
    def row_style(row):
        return [medal.get(row["Position"], "")] * len(row)
    return df.style.apply(row_style, axis=1)


display_cols = ["Position", "Abbreviation", "FullName", "TeamName", "GridPosition", "Gained", "Points", "Status"]
st.dataframe(
    style_results(results[display_cols]),
    use_container_width=True, hide_index=True,
)

# ── Key Metrics ────────────────────────────────────────────────────────────────
st.subheader("Key Stats")
c1, c2, c3 = st.columns(3)

try:
    fl_lap = session.laps.pick_fastest()
    fl_t = fl_lap["LapTime"].total_seconds()
    m, s = divmod(fl_t, 60)
    c1.metric("Fastest Lap", f"{fl_lap['Driver']}  {int(m)}:{s:06.3f}")
except Exception:
    c1.metric("Fastest Lap", "—")

gained_df = results.dropna(subset=["Gained"])
if not gained_df.empty:
    mg = gained_df.sort_values("Gained", ascending=False).iloc[0]
    val = int(mg["Gained"])
    c2.metric("Most Positions Gained", f"{mg['Abbreviation']}  {'+' if val >= 0 else ''}{val}")
else:
    c2.metric("Most Positions Gained", "—")

winner = results.iloc[0]
try:
    pole = results[results["GridPosition"] == 1].iloc[0]
    c3.metric("Pole → Winner", f"{pole['Abbreviation']} → {winner['Abbreviation']}")
except Exception:
    c3.metric("Winner", winner["Abbreviation"])

st.divider()

# ── Weather Timeline ───────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Weather Timeline")
    try:
        weather = get_weather(session)
        if not weather.empty:
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(x=weather["Time_min"], y=weather["AirTemp"],
                                       name="Air Temp (°C)", line=dict(color="#E8002D")))
            fig_w.add_trace(go.Scatter(x=weather["Time_min"], y=weather["TrackTemp"],
                                       name="Track Temp (°C)", line=dict(color="#FF8C00")))
            if weather["Rainfall"].any():
                fig_w.add_trace(go.Bar(x=weather["Time_min"],
                                       y=weather["Rainfall"].astype(float) * 5,
                                       name="Rain", marker_color="#4FC3F7", opacity=0.4))
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
        rc = get_race_control(session)
        notable = rc[rc["Message"].str.contains(
            "SAFETY CAR|VIRTUAL|RED FLAG|DRS|YELLOW|BLUE", na=False, case=False
        )].copy()

        def infer_flag(row):
            if pd.notna(row["Flag"]) and row["Flag"] not in (None, "None", ""):
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
            st.dataframe(notable[["Lap", "Flag", "Message"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("No notable race control events.")
    except Exception as e:
        st.info(f"Race control data unavailable: {e}")
