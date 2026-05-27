"""AI Race Engineer: Groq-powered chat grounded in DuckDB race data."""

from groq import Groq
from src.pipeline.db import get_results, get_weather, get_race_control, get_schedule
from src.analysis.lap_analysis import get_lap_comparison, get_consistency_score
from src.analysis.tire_analysis import get_stints

SYSTEM_PROMPT = """You are an expert F1 race engineer, analyst, and commentator with deep knowledge of Formula 1.

You have TWO sources of knowledge — use them appropriately:

## Source 1: Race Data (provided below)
Structured telemetry and timing data from the selected race. Use this for:
- Lap times, sector times, and pace comparisons
- Pit stop timing, stint lengths, and tyre compounds
- Race positions, gaps, and finishing order
- Weather conditions and safety car periods
Always cite specific lap numbers or time deltas when drawing from this data.

## Source 2: General F1 Knowledge (your training)
Background knowledge about Formula 1. Use this for:
- Driver profiles, nationalities, career histories, and championships won
- Constructor histories, car numbers, and team structures
- F1 rules, regulations, and technical concepts (DRS, undercut, deg, tyre life, etc.)
- Circuit characteristics and historical race context

## Rules
- For race-specific questions: answer from the provided race data and cite specific numbers. If the data is insufficient, say "the provided race data doesn't include enough detail to answer this."
- For general F1 knowledge questions: answer from your training, but prefix your answer with "As general F1 background:" so the user knows it is not sourced from the race data.
- If a question mixes both (e.g. "how did VER's strategy compare to his usual style?"): address the data part first, then the background part with the prefix.
- Never invent lap times, positions, or race statistics. If unsure about a specific fact, say "I'm not certain, but..." rather than stating it confidently.
- Be concise: 2–4 sentences per answer unless more detail is requested.
- Use F1 terminology naturally (undercut, overcut, deg, stint, delta, pace window, DRS train).
"""


def build_race_context(year: int, round_num: int, driver_a: str = None, driver_b: str = None) -> str:
    schedule = get_schedule(year)
    event_row = schedule[schedule["Round"] == round_num]
    event_name = event_row["EventName"].iloc[0] if not event_row.empty else f"Round {round_num}"
    circuit = event_row["Circuit"].iloc[0] if not event_row.empty else "—"
    country = event_row["Country"].iloc[0] if not event_row.empty else "—"

    lines = [
        f"# Race: {event_name} {year}",
        f"Circuit: {circuit}, {country}",
        "",
    ]

    # Race results
    try:
        results = get_results(year, round_num)
        results = results[results["Position"].notna()].copy()
        results["_pos"] = pd.to_numeric(results["Position"], errors="coerce")
        results = results.sort_values("_pos")
        lines.append("## Race Results")
        for _, r in results.head(10).iterrows():
            lines.append(f"P{int(r['_pos'])}: {r['Abbreviation']} ({r['TeamName']}) — {r['Status']}")
        lines.append("")
    except Exception:
        pass

    # Weather
    try:
        weather = get_weather(year, round_num)
        if not weather.empty:
            lines.append("## Weather")
            lines.append(
                f"Air: {weather['AirTemp'].mean():.1f}°C avg | "
                f"Track: {weather['TrackTemp'].mean():.1f}°C avg | "
                f"Rain: {'Yes' if weather['Rainfall'].any() else 'No'}"
            )
            lines.append("")
    except Exception:
        pass

    # Race control
    try:
        rc = get_race_control(year, round_num)
        sc_events = rc[rc["Message"].str.contains("SAFETY CAR|VIRTUAL|RED FLAG", na=False, case=False)]
        if not sc_events.empty:
            lines.append("## Key Race Control Events")
            for _, e in sc_events.iterrows():
                lines.append(f"Lap {e['Lap']}: {e['Message']}")
            lines.append("")
    except Exception:
        pass

    # Pit stop summary
    try:
        stints = get_stints(year, round_num)
        lines.append("## Pit Stop Summary")
        for driver in list(stints["Driver"].unique())[:10]:
            d_stints = stints[stints["Driver"] == driver]
            by_stint = d_stints.groupby("Stint").agg(
                Compound=("Compound", "first"),
                StartLap=("LapNumber", "min"),
            ).reset_index()
            stint_str = " → ".join(
                f"{row['Compound']}@L{row['StartLap']}" for _, row in by_stint.iterrows()
            )
            lines.append(f"{driver}: {stint_str}")
        lines.append("")
    except Exception:
        pass

    # Driver comparison
    if driver_a and driver_b:
        try:
            lap_comp = get_lap_comparison(year, round_num, driver_a, driver_b)
            delta_avg = lap_comp["delta"].dropna().mean()
            faster = driver_a if delta_avg < 0 else driver_b
            lines.append(f"## {driver_a} vs {driver_b}")
            lines.append(f"Average lap delta: {abs(delta_avg):.3f}s — {faster} faster overall")
            for drv in [driver_a, driver_b]:
                c = get_consistency_score(year, round_num, drv)
                if c["std"] is not None:
                    lines.append(
                        f"{drv} consistency: mean {c['mean']:.3f}s, "
                        f"std ±{c['std']:.3f}s over {c['n_laps']} clean laps"
                    )
            lines.append("")
        except Exception:
            pass

    return "\n".join(lines)


def ask_race_engineer(question: str, context: str, api_key: str):
    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context},
        {"role": "user", "content": question},
    ]
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=512,
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
