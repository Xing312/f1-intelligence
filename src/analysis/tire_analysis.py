"""Tire strategy: stint extraction, degradation regression, compound comparison."""

import numpy as np
import pandas as pd
from scipy import stats
from src.pipeline.session_loader import COMPOUND_COLORS, get_safety_car_laps


def get_stints(session) -> pd.DataFrame:
    """Extract stint data for all drivers."""
    laps = session.laps.copy()
    laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
    sc_laps = get_safety_car_laps(session)

    rows = []
    for driver in laps["Driver"].unique():
        d_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
        stint = 1
        prev_compound = None
        for _, lap in d_laps.iterrows():
            compound = lap.get("Compound", "UNKNOWN") or "UNKNOWN"
            if compound != prev_compound and prev_compound is not None:
                stint += 1
            rows.append({
                "Driver": driver,
                "Stint": stint,
                "LapNumber": int(lap["LapNumber"]),
                "LapTimeSec": lap["LapTimeSec"],
                "Compound": compound.upper(),
                "TyreLife": lap.get("TyreLife", np.nan),
                "IsPit": pd.notna(lap.get("PitInTime")),
                "IsPitOut": pd.notna(lap.get("PitOutTime")),
                "IsAccurate": bool(lap.get("IsAccurate", False)),
                "IsSC": int(lap["LapNumber"]) in sc_laps,
            })
            prev_compound = compound

    return pd.DataFrame(rows)


def degradation_slope(stint_df: pd.DataFrame) -> dict:
    """
    Linear regression of lap time vs tyre life for a single stint.
    Returns slope (s/lap), intercept, r², and filtered DataFrame.
    """
    clean = stint_df[
        stint_df["IsAccurate"]
        & ~stint_df["IsPit"]
        & ~stint_df["IsPitOut"]
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


def get_all_degradation(session) -> list[dict]:
    """Return degradation analysis for every driver/stint combination."""
    stints = get_stints(session)
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


def compound_comparison(session) -> pd.DataFrame:
    """Average clean lap pace per compound this race."""
    stints = get_stints(session)
    clean = stints[
        stints["IsAccurate"]
        & ~stints["IsPit"]
        & ~stints["IsPitOut"]
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


def pit_window_estimate(slope: float, current_lap_time: float, threshold: float = 0.5) -> int:
    """
    Estimate laps remaining before degradation causes > threshold seconds of loss.
    Returns number of additional laps, or -1 if slope is flat/negative.
    """
    if slope is None or slope <= 0:
        return -1
    laps_to_threshold = threshold / slope
    return max(0, int(laps_to_threshold))
