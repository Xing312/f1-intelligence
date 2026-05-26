"""Anomaly detection: z-score + rule-based lap flagging, reads from DuckDB."""

import numpy as np
import pandas as pd
from src.pipeline.db import get_laps, get_sc_laps

FLAG_COLORS = {
    "fastest": "#FFD700",
    "pit_in": "#FF8C00",
    "pit_out": "#FFA500",
    "safety_car": "#4FC3F7",
    "slow_outlier": "#E8002D",
    "normal": "#44FF44",
}

FLAG_LABELS = {
    "fastest": "Fastest Lap",
    "pit_in": "Pit In",
    "pit_out": "Pit Out",
    "safety_car": "Safety Car",
    "slow_outlier": "Anomaly (>3σ slow)",
    "normal": "Normal",
}


def flag_laps(year: int, round_num: int, driver: str) -> pd.DataFrame:
    laps = get_laps(year, round_num, driver).copy()
    sc_laps = get_sc_laps(year, round_num)

    accurate = laps[laps["IsAccurate"] & laps["LapTimeSec"].notna()]["LapTimeSec"]
    mean_t = accurate.mean() if len(accurate) > 0 else 0
    std_t = accurate.std() if len(accurate) > 2 else 9999

    fastest_time = accurate.min() if len(accurate) > 0 else None
    fastest_lap_num = int(laps.loc[laps["LapTimeSec"] == fastest_time, "LapNumber"].iloc[0]) if fastest_time is not None else -1

    flags = []
    for _, lap in laps.iterrows():
        lap_num = int(lap["LapNumber"])
        t = lap["LapTimeSec"]

        if lap_num == fastest_lap_num:
            flag = "fastest"
        elif bool(lap["PitIn"]):
            flag = "pit_in"
        elif bool(lap["PitOut"]):
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
            "Compound": str(lap.get("Compound", "UNKNOWN") or "UNKNOWN"),
            "TyreLife": lap.get("TyreLife", np.nan),
        })

    return pd.DataFrame(flags).sort_values("LapNumber").reset_index(drop=True)


def get_anomaly_summary(flagged: pd.DataFrame) -> pd.DataFrame:
    return flagged[flagged["Flag"] != "normal"][
        ["LapNumber", "LapTimeSec", "FlagLabel", "Compound", "TyreLife"]
    ].copy()
