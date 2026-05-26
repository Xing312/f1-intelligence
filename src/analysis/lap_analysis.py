"""Lap-level analysis reading from DuckDB."""

import pandas as pd
from src.pipeline.db import get_laps, get_sc_laps


def _clean(laps: pd.DataFrame) -> pd.DataFrame:
    return laps[
        laps["IsAccurate"]
        & laps["LapTimeSec"].notna()
        & ~laps["PitIn"]
        & ~laps["PitOut"]
    ].copy()


def get_lap_comparison(year: int, round_num: int, driver_a: str, driver_b: str) -> pd.DataFrame:
    a = get_laps(year, round_num, driver_a)[["LapNumber", "LapTimeSec"]].rename(
        columns={"LapTimeSec": driver_a}
    )
    b = get_laps(year, round_num, driver_b)[["LapNumber", "LapTimeSec"]].rename(
        columns={"LapTimeSec": driver_b}
    )
    merged = a.merge(b, on="LapNumber", how="outer").sort_values("LapNumber")
    merged["delta"] = merged[driver_a] - merged[driver_b]
    return merged


def get_sector_delta_pivot(year: int, round_num: int, driver_a: str, driver_b: str) -> pd.DataFrame:
    all_laps = get_laps(year, round_num)
    la = all_laps[all_laps["Driver"] == driver_a].set_index("LapNumber")
    lb = all_laps[all_laps["Driver"] == driver_b].set_index("LapNumber")
    common = la.index.intersection(lb.index)

    rows = []
    for lap_num in common:
        for s, col in enumerate(["Sector1TimeSec", "Sector2TimeSec", "Sector3TimeSec"], 1):
            va = la.loc[lap_num, col]
            vb = lb.loc[lap_num, col]
            if pd.notna(va) and pd.notna(vb):
                rows.append({"LapNumber": lap_num, "Sector": f"S{s}", "Delta": vb - va})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.pivot(index="LapNumber", columns="Sector", values="Delta")


def get_consistency_score(year: int, round_num: int, driver: str) -> dict:
    laps = get_laps(year, round_num, driver)
    clean = _clean(laps)
    times = clean["LapTimeSec"].dropna()
    if len(times) < 3:
        return {"mean": None, "std": None, "cv": None, "n_laps": len(times)}
    return {
        "mean": round(float(times.mean()), 3),
        "std": round(float(times.std()), 3),
        "cv": round(float(times.std() / times.mean()), 5),
        "n_laps": len(times),
    }


def auto_summary(year: int, round_num: int, driver_a: str, driver_b: str) -> str:
    all_laps = get_laps(year, round_num)
    la = all_laps[all_laps["Driver"] == driver_a]
    lb = all_laps[all_laps["Driver"] == driver_b]

    lines = []
    for s, col in enumerate(["Sector1TimeSec", "Sector2TimeSec", "Sector3TimeSec"], 1):
        common = set(la["LapNumber"]) & set(lb["LapNumber"])
        if not common:
            continue
        avg_a = la[la["LapNumber"].isin(common)][col].mean()
        avg_b = lb[lb["LapNumber"].isin(common)][col].mean()
        if pd.isna(avg_a) or pd.isna(avg_b):
            continue
        faster = driver_a if avg_a < avg_b else driver_b
        diff = abs(avg_a - avg_b)
        lines.append(f"**S{s}:** {faster} averaged {diff:.3f}s faster")

    lap_comp = get_lap_comparison(year, round_num, driver_a, driver_b)
    overall = lap_comp["delta"].dropna().mean()
    if pd.notna(overall) and abs(overall) > 0.01:
        faster = driver_a if overall < 0 else driver_b
        lines.append(f"**Overall:** {faster} had a {abs(overall):.3f}s avg lap time advantage")

    return "\n\n".join(lines) if lines else "No significant differences detected."
