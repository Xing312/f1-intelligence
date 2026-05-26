"""Fetch fastest-lap telemetry for all drivers/races and store in DuckDB."""

import fastf1
import pandas as pd
import duckdb
from pathlib import Path

CACHE_DIR = Path("cache")
DB_PATH = Path("f1.duckdb")
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS telemetry (
    Year     INT,
    Round    INT,
    Driver   VARCHAR,
    SampleIdx INT,
    Distance FLOAT,
    X        FLOAT,
    Y        FLOAT,
    Speed    FLOAT,
    Throttle FLOAT,
    nGear    INT,
    Brake    BOOLEAN
)
"""


def _extract(session, driver: str) -> pd.DataFrame:
    try:
        lap = session.laps.pick_driver(driver).pick_fastest()
        tel = lap.get_telemetry().add_distance()
        try:
            pos = lap.get_pos_data()
            tel = tel.merge_channels(pos)
        except Exception:
            pass
        keep = [c for c in ["X", "Y", "Speed", "Throttle", "nGear", "Brake", "Distance"]
                if c in tel.columns]
        df = tel[keep].copy()
        df["Driver"] = driver
        df["Year"] = int(session.event["EventDate"].year)
        df["Round"] = int(session.event["RoundNumber"])
        df["SampleIdx"] = range(len(df))
        for col in ["X", "Y", "Speed", "Throttle", "nGear", "Brake"]:
            if col not in df.columns:
                df[col] = None
        return df[["Year", "Round", "Driver", "SampleIdx", "Distance",
                    "X", "Y", "Speed", "Throttle", "nGear", "Brake"]]
    except Exception as e:
        print(f"    {driver}: skipped — {e}")
        return pd.DataFrame()


def fetch_telemetry(years: list, db_path: Path = DB_PATH):
    con = duckdb.connect(str(db_path))
    con.execute(CREATE_TABLE)

    for year in years:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            round_num = int(event["RoundNumber"])
            existing = con.execute(
                "SELECT COUNT(*) FROM telemetry WHERE Year=? AND Round=?",
                [year, round_num],
            ).fetchone()[0]
            if existing > 0:
                print(f"[{year}] R{round_num:02d} already stored, skipping")
                continue

            print(f"[{year}] R{round_num:02d} {event['EventName']} — loading telemetry…")
            try:
                session = fastf1.get_session(year, round_num, "R")
                session.load(laps=True, telemetry=True, weather=False, messages=False)
                drivers = session.laps["Driver"].unique().tolist()
                rows = [_extract(session, d) for d in drivers]
                combined = pd.concat([r for r in rows if not r.empty], ignore_index=True)
                if not combined.empty:
                    con.execute("INSERT INTO telemetry SELECT * FROM combined")
                    print(f"  ✓ {len(drivers)} drivers, {len(combined):,} samples")
            except Exception as e:
                print(f"  skipped — {e}")

    con.close()
    print("Done.")


if __name__ == "__main__":
    import sys
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2024]
    fetch_telemetry(years)
