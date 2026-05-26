"""Anomaly detection: z-score + rule-based lap flagging."""

import numpy as np
import pandas as pd
from src.pipeline.session_loader import get_safety_car_laps


FLAG_COLORS = {
    "fastest": "#FFD700",
    "pit_in": "#FF8C00",
    "pit_out": "#FFA500",
    "safety_car": "#4FC3F7",
    "slow_outlier": "#E8002D",
    "normal": "#44FF44",
}

FLAG_LABELS = {
    "fastest": "⚪ Fastest Lap",
    "pit_in": "🟡 Pit In",
    "pit_out": "🟡 Pit Out",
    "safety_car": "🔵 Safety Car",
    "slow_outlier": "🔴 Anomaly (>3σ slow)",
    "normal": "Normal",
}


def flag_laps(session, driver: str) -> pd.DataFrame:
    """
    Return per-lap DataFrame with flag_type column.
    Priority: fastest > pit_in > pit_out > safety_car > slow_outlier > normal
    """
    laps = session.laps.pick_driver(driver).copy()
    laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
    sc_laps = get_safety_car_laps(session)

    # Fastest lap
    try:
        fastest_lap_num = int(laps.pick_fastest()["LapNumber"])
    except Exception:
        fastest_lap_num = -1

    # Z-score on accurate laps
    accurate = laps[laps["IsAccurate"] & laps["LapTimeSec"].notna()]["LapTimeSec"]
    mean_t = accurate.mean()
    std_t = accurate.std() if len(accurate) > 2 else 9999

    flags = []
    for _, lap in laps.iterrows():
        lap_num = int(lap["LapNumber"])
        t = lap["LapTimeSec"]

        if lap_num == fastest_lap_num:
            flag = "fastest"
        elif pd.notna(lap.get("PitInTime")):
            flag = "pit_in"
        elif pd.notna(lap.get("PitOutTime")):
            flag = "pit_out"
        elif lap_num in sc_laps:
            flag = "safety_car"
        elif pd.notna(t) and std_t > 0 and (t - mean_t) / std_t > 3:
            flag = "slow_outlier"
        else:
            flag = "normal"

        flags.append({
            "LapNumber": lap_num,
            "LapTimeSec": t,
            "Flag": flag,
            "FlagLabel": FLAG_LABELS[flag],
            "Color": FLAG_COLORS[flag],
            "Compound": lap.get("Compound", "UNKNOWN"),
            "TyreLife": lap.get("TyreLife", np.nan),
        })

    return pd.DataFrame(flags).sort_values("LapNumber").reset_index(drop=True)


def get_anomaly_summary(flagged: pd.DataFrame) -> pd.DataFrame:
    """Return only non-normal laps with explanation."""
    return flagged[flagged["Flag"] != "normal"][
        ["LapNumber", "LapTimeSec", "FlagLabel", "Compound", "TyreLife"]
    ].copy()
