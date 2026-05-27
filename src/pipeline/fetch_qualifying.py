"""Fetch qualifying session data via FastF1 and persist to DuckDB."""

import time
import fastf1
import pandas as pd
import duckdb
from pathlib import Path

CACHE_DIR = Path("cache")
DB_PATH = Path("f1.duckdb")
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


def extract_qualifying_results(session) -> pd.DataFrame:
    cols = ["DriverNumber", "Abbreviation", "FullName", "TeamName",
            "Position", "Q1", "Q2", "Q3"]
    available = [c for c in cols if c in session.results.columns]
    df = session.results[available].copy()
    for q in ["Q1", "Q2", "Q3"]:
        if q in df.columns:
            df[f"{q}Sec"] = pd.to_timedelta(df[q], errors="coerce").dt.total_seconds()
        else:
            df[f"{q}Sec"] = None
    df = df.drop(columns=[c for c in ["Q1", "Q2", "Q3"] if c in df.columns])
    df["Year"] = session.event["EventDate"].year
    df["Round"] = int(session.event["RoundNumber"])
    df["EventName"] = session.event["EventName"]
    df["Circuit"] = session.event["Location"]
    df["Country"] = session.event["Country"]
    return df


def extract_qualifying_laps(session) -> pd.DataFrame:
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


def _upsert(con, df: pd.DataFrame, table: str):
    if df.empty:
        return
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0")
    con.execute(f"INSERT INTO {table} SELECT * FROM df")


def fetch_qualifying(years: list, db_path: Path = DB_PATH):
    CACHE_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(db_path))
    tables = con.execute("SHOW TABLES").df()["name"].tolist()

    for year in years:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            round_num = int(event["RoundNumber"])
            existing = (
                con.execute(
                    "SELECT COUNT(*) FROM qualifying_results WHERE Year=? AND Round=?",
                    [year, round_num],
                ).fetchone()[0]
                if "qualifying_results" in tables
                else 0
            )
            if existing > 0:
                print(f"[{year}] R{round_num:02d}: already stored, skipping")
                continue
            print(f"[{year}] R{round_num:02d} {event['EventName']}")
            try:
                session = fastf1.get_session(year, round_num, "Q")
                session.load(laps=True, telemetry=False, weather=False, messages=False)
                _upsert(con, extract_qualifying_results(session), "qualifying_results")
                _upsert(con, extract_qualifying_laps(session), "qualifying_laps")
                tables = con.execute("SHOW TABLES").df()["name"].tolist()
                print(f"  ✓ saved")
                time.sleep(8)
            except Exception as e:
                print(f"  Skipped — {e}")
                time.sleep(30)

    con.close()
    print(f"Done.")


if __name__ == "__main__":
    import sys
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2024]
    fetch_qualifying(years)
