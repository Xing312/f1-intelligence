"""FastF1 session loader with caching and helper extractors."""

import os
import fastf1
import pandas as pd
import duckdb
from pathlib import Path

# Use /tmp on cloud, local cache/ otherwise
_cache_candidates = [Path("/tmp/fastf1_cache"), Path("cache")]
CACHE_DIR = next((p for p in _cache_candidates if os.access(str(p.parent), os.W_OK)), Path("/tmp/fastf1_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# Compound color map for consistent styling
COMPOUND_COLORS = {
    "SOFT": "#E8002D",
    "MEDIUM": "#FFF200",
    "HARD": "#FFFFFF",
    "INTERMEDIATE": "#39B54A",
    "WET": "#0067FF",
    "UNKNOWN": "#999999",
}


def load_session(year: int, round_num: int, session_type: str = "R") -> fastf1.core.Session:
    """Load and cache a FastF1 session. session_type: R=Race, Q=Qualifying."""
    session = fastf1.get_session(year, round_num, session_type)
    session.load(
        laps=True,
        telemetry=True,
        weather=True,
        messages=True,
        livedata=None,
    )
    return session


def get_drivers(session) -> list[dict]:
    """Return list of {abbr, full_name, team} dicts for all drivers in session."""
    results = session.results
    drivers = []
    for _, row in results.iterrows():
        drivers.append({
            "abbr": row["Abbreviation"],
            "full_name": row["FullName"],
            "team": row["TeamName"],
        })
    return drivers


def _db_path() -> Path:
    candidates = [Path("f1.duckdb"), Path(__file__).parents[2] / "f1.duckdb"]
    for p in candidates:
        if p.exists():
            return p
    return Path("f1.duckdb")


def get_race_control(session) -> pd.DataFrame:
    """Race control messages — read from DuckDB if available, else from session."""
    year = session.event["EventDate"].year
    round_num = int(session.event["RoundNumber"])
    try:
        con = duckdb.connect(str(_db_path()), read_only=True)
        df = con.execute(
            "SELECT * FROM race_control WHERE Year=? AND Round=? ORDER BY Lap",
            [year, round_num]
        ).df()
        con.close()
        if not df.empty:
            return df
    except Exception:
        pass
    # Fallback: live session
    msgs = session.race_control_messages.copy()
    if msgs.empty:
        return pd.DataFrame(columns=["Lap", "Category", "Message", "Flag"])
    msgs = msgs[["Lap", "Category", "Message", "Flag"]].copy()
    msgs["Lap"] = msgs["Lap"].fillna(0).astype(int)
    return msgs.sort_values("Lap").reset_index(drop=True)


def get_safety_car_laps(session) -> set[int]:
    """Return set of lap numbers affected by Safety Car or VSC."""
    rc = get_race_control(session)
    sc_laps = set()
    if rc.empty:
        return sc_laps
    sc_events = rc[rc["Message"].str.contains("SAFETY CAR|VIRTUAL SAFETY CAR", na=False, case=False)]
    for _, row in sc_events.iterrows():
        sc_laps.add(int(row["Lap"]))
    return sc_laps


def get_weather(session) -> pd.DataFrame:
    """Weather data — read from DuckDB if available, else from session."""
    year = session.event["EventDate"].year
    round_num = int(session.event["RoundNumber"])
    try:
        con = duckdb.connect(str(_db_path()), read_only=True)
        df = con.execute(
            "SELECT * FROM weather_data WHERE Year=? AND Round=?",
            [year, round_num]
        ).df()
        con.close()
        if not df.empty:
            df = df.rename(columns={"TimeMin": "Time_min"})
            return df
    except Exception:
        pass
    # Fallback: live session
    w = session.weather_data.copy()
    if w.empty:
        return w
    w["Time_min"] = w["Time"].dt.total_seconds() / 60
    return w.reset_index(drop=True)


def get_fastest_lap(session, driver: str):
    """Return the fastest lap object for a driver."""
    return session.laps.pick_driver(driver).pick_fastest()


def get_telemetry(lap) -> pd.DataFrame:
    """Merged telemetry + position with distance column."""
    try:
        tel = lap.get_telemetry().add_distance()
        pos = lap.get_pos_data()
        # Merge on time index (nearest)
        tel = tel.merge_channels(pos)
    except Exception:
        tel = lap.get_telemetry().add_distance()
    return tel


def get_round_schedule(year: int) -> pd.DataFrame:
    """Return event schedule for a year (no testing rounds)."""
    return fastf1.get_event_schedule(year, include_testing=False)[
        ["RoundNumber", "EventName", "Location", "Country", "EventDate"]
    ]
