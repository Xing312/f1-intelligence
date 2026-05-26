"""Lap-level analysis: comparison, sector deltas, consistency."""

import numpy as np
import pandas as pd


def _clean_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Filter out pit, SC, and inaccurate laps."""
    mask = (
        laps["IsAccurate"]
        & laps["LapTime"].notna()
        & ~laps["PitInTime"].notna()
        & ~laps["PitOutTime"].notna()
    )
    return laps[mask].copy()


def get_lap_times(session, driver: str) -> pd.DataFrame:
    """Return per-lap times in seconds for a driver, with SC flag."""
    laps = session.laps.pick_driver(driver)[
        ["LapNumber", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time",
         "IsAccurate", "PitInTime", "PitOutTime", "Compound", "TyreLife"]
    ].copy()
    for col in ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]:
        laps[f"{col}Sec"] = laps[col].dt.total_seconds()
    laps["Driver"] = driver
    return laps.reset_index(drop=True)


def get_lap_comparison(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """Merge lap times for two drivers side by side."""
    a = get_lap_times(session, driver_a)[["LapNumber", "LapTimeSec"]].rename(
        columns={"LapTimeSec": driver_a}
    )
    b = get_lap_times(session, driver_b)[["LapNumber", "LapTimeSec"]].rename(
        columns={"LapTimeSec": driver_b}
    )
    merged = a.merge(b, on="LapNumber", how="outer").sort_values("LapNumber")
    merged["delta"] = merged[driver_a] - merged[driver_b]
    return merged


def get_sector_delta(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """
    Sector-level delta: positive = driver_a faster (lower time), negative = driver_b faster.
    Returns long-form DataFrame with columns: LapNumber, Sector, Delta
    """
    rows = []
    laps_a = session.laps.pick_driver(driver_a)
    laps_b = session.laps.pick_driver(driver_b)

    for lap_num in sorted(set(laps_a["LapNumber"]) & set(laps_b["LapNumber"])):
        la = laps_a[laps_a["LapNumber"] == lap_num].iloc[0]
        lb = laps_b[laps_b["LapNumber"] == lap_num].iloc[0]
        for s, col in enumerate(["Sector1Time", "Sector2Time", "Sector3Time"], 1):
            if pd.notna(la[col]) and pd.notna(lb[col]):
                delta = lb[col].total_seconds() - la[col].total_seconds()
                rows.append({"LapNumber": lap_num, "Sector": f"S{s}", "Delta": delta})

    return pd.DataFrame(rows)


def get_sector_delta_pivot(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """Pivot sector delta: index=LapNumber, columns=S1/S2/S3."""
    df = get_sector_delta(session, driver_a, driver_b)
    if df.empty:
        return df
    return df.pivot(index="LapNumber", columns="Sector", values="Delta")


def get_consistency_score(session, driver: str) -> dict:
    """Lap time consistency: mean, std, CV of clean laps."""
    laps = get_lap_times(session, driver)
    clean = _clean_laps(laps)
    times = clean["LapTimeSec"].dropna()
    if len(times) < 3:
        return {"mean": None, "std": None, "cv": None, "n_laps": len(times)}
    return {
        "mean": round(times.mean(), 3),
        "std": round(times.std(), 3),
        "cv": round(times.std() / times.mean(), 5),
        "n_laps": len(times),
    }


def auto_summary(session, driver_a: str, driver_b: str) -> str:
    """Generate a short text summary of sector-level advantages."""
    delta = get_sector_delta(session, driver_a, driver_b)
    if delta.empty:
        return "Insufficient data for comparison."

    lines = []
    for sector in ["S1", "S2", "S3"]:
        s = delta[delta["Sector"] == sector]["Delta"]
        if s.empty:
            continue
        avg = s.mean()
        faster = driver_a if avg > 0 else driver_b
        slower = driver_b if avg > 0 else driver_a
        lines.append(
            f"**{sector}:** {faster} averaged {abs(avg):.3f}s faster than {slower}"
        )

    # Overall
    laps = get_lap_comparison(session, driver_a, driver_b)
    overall = laps["delta"].dropna().mean()
    if abs(overall) > 0.01:
        faster_overall = driver_a if overall < 0 else driver_b
        lines.append(
            f"**Overall:** {faster_overall} had a {abs(overall):.3f}s average lap time advantage"
        )

    return "\n\n".join(lines) if lines else "No significant differences detected."
