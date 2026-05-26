"""Tire strategy analysis reading from DuckDB."""

import numpy as np
import pandas as pd
from scipy import stats
from src.pipeline.db import get_laps, get_sc_laps

COMPOUND_COLORS = {
    "SOFT": "#E8002D",
    "MEDIUM": "#FFF200",
    "HARD": "#FFFFFF",
    "INTERMEDIATE": "#39B54A",
    "WET": "#0067FF",
    "UNKNOWN": "#999999",
}


def get_stints(year: int, round_num: int) -> pd.DataFrame:
    laps = get_laps(year, round_num)
    sc_laps = get_sc_laps(year, round_num)
    laps["IsSC"] = laps["LapNumber"].isin(sc_laps)
    laps["Compound"] = laps["Compound"].fillna("UNKNOWN").str.upper()

    rows = []
    for driver in laps["Driver"].unique():
        d = laps[laps["Driver"] == driver].sort_values("LapNumber")
        stint = 1
        prev = None
        for _, row in d.iterrows():
            c = row["Compound"]
            if c != prev and prev is not None:
                stint += 1
            rows.append({
                "Driver": driver,
                "Stint": stint,
                "LapNumber": int(row["LapNumber"]),
                "LapTimeSec": row["LapTimeSec"],
                "Compound": c,
                "TyreLife": row["TyreLife"],
                "PitIn": bool(row["PitIn"]),
                "PitOut": bool(row["PitOut"]),
                "IsAccurate": bool(row["IsAccurate"]),
                "IsSC": bool(row["IsSC"]),
            })
            prev = c
    return pd.DataFrame(rows)


def degradation_slope(stint_df: pd.DataFrame) -> dict:
    clean = stint_df[
        stint_df["IsAccurate"]
        & ~stint_df["PitIn"]
        & ~stint_df["PitOut"]
        & ~stint_df["IsSC"]
        & stint_df["LapTimeSec"].notna()
        & stint_df["TyreLife"].notna()
    ].copy()

    if len(clean) < 3:
        return {"slope": None, "intercept": None, "r2": None, "laps": clean}

    x = clean["TyreLife"].values.astype(float)
    y = clean["LapTimeSec"].values.astype(float)
    slope, intercept, r, _, _ = stats.linregress(x, y)
    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 3),
        "r2": round(r ** 2, 4),
        "laps": clean,
    }


def get_all_degradation(year: int, round_num: int) -> list[dict]:
    stints = get_stints(year, round_num)
    results = []
    for driver in stints["Driver"].unique():
        d = stints[stints["Driver"] == driver]
        for stint_num in d["Stint"].unique():
            s = d[d["Stint"] == stint_num]
            compound = s["Compound"].iloc[0]
            reg = degradation_slope(s)
            results.append({
                "Driver": driver,
                "Stint": stint_num,
                "Compound": compound,
                "Color": COMPOUND_COLORS.get(compound, "#999"),
                "StartLap": int(s["LapNumber"].min()),
                "EndLap": int(s["LapNumber"].max()),
                "Laps": len(s),
                "Slope": reg["slope"],
                "Intercept": reg["intercept"],
                "R2": reg["r2"],
                "CleanLaps": reg["laps"],
            })
    return results


def compound_comparison(year: int, round_num: int) -> pd.DataFrame:
    stints = get_stints(year, round_num)
    clean = stints[
        stints["IsAccurate"]
        & ~stints["PitIn"]
        & ~stints["PitOut"]
        & ~stints["IsSC"]
        & stints["LapTimeSec"].notna()
    ]
    summary = (
        clean.groupby("Compound")["LapTimeSec"]
        .agg(avg_lap="mean", laps="count", std="std")
        .reset_index()
        .sort_values("avg_lap")
    )
    summary["Color"] = summary["Compound"].map(COMPOUND_COLORS)
    return summary


def pit_window_estimate(slope: float, threshold: float = 0.5) -> int:
    if slope is None or slope <= 0:
        return -1
    return max(0, int(threshold / slope))
