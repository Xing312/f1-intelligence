"""FastF1 session loader with caching and helper extractors."""

import os
import fastf1
import pandas as pd
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


def get_race_control(session) -> pd.DataFrame:
    """Race control messages: Safety Car, VSC, yellow flags, DRS."""
    msgs = session.race_control_messages.copy()
    if msgs.empty:
        return pd.DataFrame(columns=["Time", "Lap", "Category", "Message", "Flag"])
    msgs = msgs[["Time", "Lap", "Category", "Message", "Flag"]].copy()
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
    """Weather data: AirTemp, TrackTemp, Humidity, Rainfall, WindSpeed."""
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
