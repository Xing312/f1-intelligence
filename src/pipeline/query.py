"""Reusable DuckDB query helpers used by both notebooks and Streamlit pages."""

import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path("f1.duckdb")


def _q(sql: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    df = con.execute(sql).df()
    con.close()
    return df


def available_years(db_path: Path = DB_PATH) -> list[int]:
    df = _q("SELECT DISTINCT Year FROM race_results ORDER BY Year DESC", db_path)
    return df["Year"].tolist()


def available_events(year: int, db_path: Path = DB_PATH) -> list[str]:
    df = _q(f"SELECT DISTINCT EventName FROM race_results WHERE Year={year} ORDER BY Round", db_path)
    return df["EventName"].tolist()


def driver_season_summary(year: int, db_path: Path = DB_PATH) -> pd.DataFrame:
    return _q(f"""
        SELECT
            Abbreviation,
            FullName,
            TeamName,
            COUNT(*) AS races,
            SUM(Points) AS total_points,
            SUM(CASE WHEN CAST(Position AS INT) = 1 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN CAST(Position AS INT) <= 3 THEN 1 ELSE 0 END) AS podiums,
            ROUND(AVG(CAST(Position AS FLOAT)), 2) AS avg_finish
        FROM race_results
        WHERE Year = {year}
        GROUP BY Abbreviation, FullName, TeamName
        ORDER BY total_points DESC
    """, db_path)


def team_season_summary(year: int, db_path: Path = DB_PATH) -> pd.DataFrame:
    return _q(f"""
        SELECT
            TeamName,
            SUM(Points) AS total_points,
            SUM(CASE WHEN CAST(Position AS INT) = 1 THEN 1 ELSE 0 END) AS wins,
            ROUND(AVG(CAST(Position AS FLOAT)), 2) AS avg_finish
        FROM race_results
        WHERE Year = {year}
        GROUP BY TeamName
        ORDER BY total_points DESC
    """, db_path)


def race_results(year: int, event_name: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    return _q(f"""
        SELECT Abbreviation, FullName, TeamName, GridPosition,
               Position, Points, Status
        FROM race_results
        WHERE Year = {year} AND EventName = '{event_name}'
        ORDER BY CAST(Position AS FLOAT)
    """, db_path)


def lap_times(year: int, event_name: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    return _q(f"""
        SELECT Driver, Team, LapNumber, LapTimeSec,
               Sector1TimeSec, Sector2TimeSec, Sector3TimeSec,
               Compound, TyreLife, SpeedFL, IsAccurate
        FROM lap_data
        WHERE Year = {year} AND EventName = '{event_name}' AND IsAccurate = true
        ORDER BY Driver, LapNumber
    """, db_path)


def driver_head_to_head(year: int, driver1: str, driver2: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    return _q(f"""
        SELECT r.Round, r.EventName,
               MAX(CASE WHEN r.Abbreviation = '{driver1}' THEN CAST(r.Position AS INT) END) AS {driver1}_pos,
               MAX(CASE WHEN r.Abbreviation = '{driver2}' THEN CAST(r.Position AS INT) END) AS {driver2}_pos,
               MAX(CASE WHEN r.Abbreviation = '{driver1}' THEN r.Points END) AS {driver1}_pts,
               MAX(CASE WHEN r.Abbreviation = '{driver2}' THEN r.Points END) AS {driver2}_pts
        FROM race_results r
        WHERE Year = {year} AND Abbreviation IN ('{driver1}', '{driver2}')
        GROUP BY r.Round, r.EventName
        ORDER BY r.Round
    """, db_path)
