"""Fetch F1 session data via FastF1 and persist to DuckDB."""

import fastf1
import pandas as pd
import duckdb
from pathlib import Path

CACHE_DIR = Path("cache")
DB_PATH = Path("f1.duckdb")

CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


def get_session(year: int, round_num: int, session_type: str = "R"):
    session = fastf1.get_session(year, round_num, session_type)
    session.load()
    return session


def extract_race_results(session) -> pd.DataFrame:
    df = session.results[
        ["DriverNumber", "Abbreviation", "FullName", "TeamName",
         "GridPosition", "Position", "Points", "Status"]
    ].copy()
    df["Year"] = session.event["EventDate"].year
    df["Round"] = int(session.event["RoundNumber"])
    df["EventName"] = session.event["EventName"]
    df["Circuit"] = session.event["Location"]
    df["Country"] = session.event["Country"]
    return df


def extract_lap_data(session) -> pd.DataFrame:
    laps = session.laps[
        ["Driver", "Team", "LapNumber", "LapTime",
         "Sector1Time", "Sector2Time", "Sector3Time",
         "Compound", "TyreLife", "SpeedFL", "IsAccurate"]
    ].copy()
    laps["Year"] = session.event["EventDate"].year
    laps["Round"] = int(session.event["RoundNumber"])
    laps["EventName"] = session.event["EventName"]
    for col in ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]:
        laps[f"{col}Sec"] = laps[col].dt.total_seconds()
    laps = laps.drop(columns=["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"])
    return laps


def _upsert(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, table: str):
    """Create table if needed, then append rows."""
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0")
    con.execute(f"INSERT INTO {table} SELECT * FROM df")


def fetch_season(year: int, db_path: Path = DB_PATH):
    CACHE_DIR.mkdir(exist_ok=True)
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    con = duckdb.connect(str(db_path))

    for _, event in schedule.iterrows():
        round_num = event["RoundNumber"]
        print(f"[{year}] Round {round_num}: {event['EventName']}")
        try:
            session = get_session(year, int(round_num), "R")
            _upsert(con, extract_race_results(session), "race_results")
            _upsert(con, extract_lap_data(session), "lap_data")
        except Exception as e:
            print(f"  Skipped — {e}")

    con.close()
    print(f"Done: {year}")


if __name__ == "__main__":
    import sys
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2022, 2023, 2024]
    for yr in years:
        fetch_season(yr)
