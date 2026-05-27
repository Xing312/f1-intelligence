import sys
import importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

import src.pipeline.db as _db
importlib.reload(_db)
from src.pipeline.db import available_years, get_season_results

st.set_page_config(page_title="Season Dashboard", page_icon="🏆", layout="wide")
st.title("🏆 Season Dashboard")

# ── Year selector ──────────────────────────────────────────────────────────────
years = available_years()
year = st.selectbox("Season", years, key="season_year")

@st.cache_data(show_spinner="Loading season data…")
def _load(yr: int) -> pd.DataFrame:
    return get_season_results(yr)

df = _load(year)
if df.empty:
    st.error("No data found for this season.")
    st.stop()

df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
df["Points"] = pd.to_numeric(df["Points"], errors="coerce").fillna(0)
df["Round"] = df["Round"].astype(int)

# Ordered list of rounds for x-axis labels
rounds = df[["Round", "EventName"]].drop_duplicates().sort_values("Round")
round_labels = {int(r["Round"]): r["EventName"].replace(" Grand Prix", " GP")
                for _, r in rounds.iterrows()}

# ── Tab layout ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Points Progression", "Race Results Heatmap", "Championship Standings"])

# ── Tab 1: Points progression ─────────────────────────────────────────────────
with tab1:
    view = st.radio("View by", ["Driver", "Constructor"], horizontal=True, key="points_view")

    if view == "Driver":
        cumulative = (
            df.sort_values("Round")
            .groupby("Abbreviation", group_keys=False)
            .apply(lambda g: g.assign(CumPoints=g["Points"].cumsum()))
        )
        final_order = (
            cumulative.groupby("Abbreviation")["CumPoints"].max()
            .sort_values(ascending=False)
        )
        top_n = st.slider("Show top N drivers", 5, 20, 10, key="top_drivers")
        top_drivers = final_order.head(top_n).index.tolist()
        plot_df = cumulative[cumulative["Abbreviation"].isin(top_drivers)]

        fig = go.Figure()
        colors = px.colors.qualitative.Plotly + px.colors.qualitative.D3
        for i, drv in enumerate(top_drivers):
            d = plot_df[plot_df["Abbreviation"] == drv].sort_values("Round")
            fig.add_trace(go.Scatter(
                x=d["Round"], y=d["CumPoints"],
                mode="lines+markers", name=drv,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{drv}</b><br>%{{x}}: %{{y}} pts<extra></extra>",
            ))
    else:
        team_pts = (
            df.groupby(["Round", "TeamName"])["Points"].sum().reset_index()
        )
        team_pts = team_pts.sort_values("Round")
        cumulative_team = (
            team_pts.groupby("TeamName", group_keys=False)
            .apply(lambda g: g.assign(CumPoints=g["Points"].cumsum()))
        )
        final_order = (
            cumulative_team.groupby("TeamName")["CumPoints"].max()
            .sort_values(ascending=False)
        )
        teams = final_order.index.tolist()
        colors = px.colors.qualitative.Plotly + px.colors.qualitative.D3

        fig = go.Figure()
        for i, team in enumerate(teams):
            d = cumulative_team[cumulative_team["TeamName"] == team].sort_values("Round")
            fig.add_trace(go.Scatter(
                x=d["Round"], y=d["CumPoints"],
                mode="lines+markers", name=team,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{team}</b><br>%{{x}}: %{{y}} pts<extra></extra>",
            ))

    fig.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=list(round_labels.keys()),
            ticktext=list(round_labels.values()),
            tickangle=-45,
            title="Round",
        ),
        yaxis_title="Cumulative Points",
        legend=dict(orientation="v", x=1.01),
        height=520,
        margin=dict(l=40, r=160, t=20, b=120),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Results heatmap ────────────────────────────────────────────────────
with tab2:
    st.caption("Finishing position per driver per round. Grey = DNF / DNS.")

    finished = df[df["Position"].notna()].copy()
    pivot = finished.pivot_table(
        index="Abbreviation", columns="Round", values="Position", aggfunc="min"
    )
    # Order drivers by total points descending
    driver_order = (
        df.groupby("Abbreviation")["Points"].sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    pivot = pivot.reindex([d for d in driver_order if d in pivot.index])

    x_labels = [round_labels.get(c, str(c)) for c in pivot.columns]

    fig2 = go.Figure(go.Heatmap(
        z=pivot.values,
        x=x_labels,
        y=pivot.index.tolist(),
        colorscale=[
            [0.0,  "#2ecc71"],
            [0.1,  "#27ae60"],
            [0.25, "#f1c40f"],
            [0.5,  "#e67e22"],
            [1.0,  "#e74c3c"],
        ],
        reversescale=False,
        zmin=1, zmax=20,
        text=pivot.values,
        texttemplate="%{text:.0f}",
        hovertemplate="<b>%{y}</b> — %{x}<br>P%{z:.0f}<extra></extra>",
        showscale=True,
        colorbar=dict(title="Position", tickvals=[1, 5, 10, 15, 20]),
    ))
    fig2.update_layout(
        height=600,
        margin=dict(l=40, r=40, t=20, b=80),
        xaxis=dict(tickangle=-45),
        yaxis=dict(title="Driver"),
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Tab 3: Championship standings snapshot ────────────────────────────────────
with tab3:
    max_round = int(df["Round"].max())
    snap_round = st.slider("Standings after round", 1, max_round, max_round, key="snap_round")

    snap = df[df["Round"] <= snap_round]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Drivers")
        drv_standings = (
            snap.groupby(["Abbreviation", "FullName"])["Points"]
            .sum().reset_index()
            .sort_values("Points", ascending=False)
            .reset_index(drop=True)
        )
        drv_standings.index += 1
        drv_standings.columns = ["Driver", "Full Name", "Points"]
        st.dataframe(drv_standings, use_container_width=True, height=560)

    with col2:
        st.subheader("Constructors")
        con_standings = (
            snap.groupby("TeamName")["Points"]
            .sum().reset_index()
            .sort_values("Points", ascending=False)
            .reset_index(drop=True)
        )
        con_standings.index += 1
        con_standings.columns = ["Constructor", "Points"]
        st.dataframe(con_standings, use_container_width=True, height=560)
