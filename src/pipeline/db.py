"""DuckDB query layer — single source of truth for all static race data."""

import duckdb
import pandas as pd
from pathlib import Path


def db_path() -> Path:
    candidates = [
        Path("f1.duckdb"),
        Path(__file__).parents[2] / "f1.duckdb",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("f1.duckdb not found")


def _q(sql: str, params=None) -> pd.DataFrame:
    con = duckdb.connect(str(db_path()), read_only=True)
    df = con.execute(sql, params or []).df()
    con.close()
    return df


def available_years() -> list[int]:
    return _q("SELECT DISTINCT Year FROM race_results ORDER BY Year DESC")["Year"].tolist()


def get_schedule(year: int) -> pd.DataFrame:
    return _q(
        "SELECT DISTINCT Round, EventName, Circuit, Country FROM race_results WHERE Year=? ORDER BY Round ASC",
        [year]
    )


def get_results(year: int, round_num: int) -> pd.DataFrame:
    return _q(
        "SELECT DISTINCT * FROM race_results WHERE Year=? AND Round=? ORDER BY CAST(Position AS FLOAT)",
        [year, round_num]
    )


def get_laps(year: int, round_num: int, driver: str = None) -> pd.DataFrame:
    if driver:
        return _q(
            "SELECT * FROM lap_data WHERE Year=? AND Round=? AND Driver=? ORDER BY LapNumber",
            [year, round_num, driver]
        )
    return _q(
        "SELECT * FROM lap_data WHERE Year=? AND Round=? ORDER BY Driver, LapNumber",
        [year, round_num]
    )


def get_weather(year: int, round_num: int) -> pd.DataFrame:
    return _q(
        "SELECT * FROM weather_data WHERE Year=? AND Round=? ORDER BY TimeMin",
        [year, round_num]
    )


def get_race_control(year: int, round_num: int) -> pd.DataFrame:
    return _q(
        "SELECT * FROM race_control WHERE Year=? AND Round=? ORDER BY Lap",
        [year, round_num]
    )


def get_sc_laps(year: int, round_num: int) -> set[int]:
    rc = get_race_control(year, round_num)
    if rc.empty:
        return set()
    sc = rc[rc["Message"].str.contains("SAFETY CAR|VIRTUAL SAFETY CAR", na=False, case=False)]
    return set(sc["Lap"].astype(int).tolist())


def get_telemetry(year: int, round_num: int, driver: str = None) -> pd.DataFrame:
    if driver:
        return _q(
            "SELECT * FROM telemetry WHERE Year=? AND Round=? AND Driver=? ORDER BY SampleIdx",
            [year, round_num, driver],
        )
    fl = fastest_lap(year, round_num)
    if fl is None:
        return pd.DataFrame()
    return _q(
        "SELECT * FROM telemetry WHERE Year=? AND Round=? AND Driver=? ORDER BY SampleIdx",
        [year, round_num, fl["Driver"]],
    )


def get_drivers(year: int, round_num: int) -> list[str]:
    df = _q(
        "SELECT DISTINCT Driver FROM lap_data WHERE Year=? AND Round=? ORDER BY Driver",
        [year, round_num]
    )
    return df["Driver"].tolist()


def fastest_lap(year: int, round_num: int, driver: str = None) -> pd.Series:
    laps = get_laps(year, round_num, driver)
    clean = laps[laps["IsAccurate"] & laps["LapTimeSec"].notna() & ~laps["PitIn"] & ~laps["PitOut"]]
    if clean.empty:
        return None
    return clean.loc[clean["LapTimeSec"].idxmin()]
