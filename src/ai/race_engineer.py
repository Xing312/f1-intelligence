"""AI Race Engineer: Groq-powered chat grounded in structured race data."""

import os
from groq import Groq
from src.analysis.lap_analysis import get_lap_comparison, get_consistency_score
from src.analysis.tire_analysis import get_stints
from src.pipeline.session_loader import get_race_control, get_weather

SYSTEM_PROMPT = """You are an expert F1 race engineer and data analyst. You are given structured data from a specific race and must answer questions about it accurately and concisely.

Rules:
- Base your answers strictly on the provided race data
- Reference specific lap numbers, time deltas, and events when relevant
- If data is insufficient to answer, say so clearly
- Be concise: 2-4 sentences per answer unless more detail is requested
- Use F1 terminology naturally (undercut, deg, stint, delta, pace window)
"""


def build_race_context(session, driver_a: str = None, driver_b: str = None) -> str:
    """Build structured context string from race data for the AI prompt."""
    event = session.event
    lines = [
        f"# Race: {event['EventName']} {event['EventDate'].year}",
        f"Circuit: {event['Location']}, {event['Country']}",
        "",
    ]

    # Race results
    results = session.results[["Position", "Abbreviation", "FullName", "TeamName", "Points", "Status"]].copy()
    results = results[results["Position"].notna()].sort_values("Position")
    lines.append("## Race Results")
    for _, r in results.head(10).iterrows():
        lines.append(f"P{int(r['Position'])}: {r['Abbreviation']} ({r['TeamName']}) — {r['Status']}")
    lines.append("")

    # Weather summary
    try:
        weather = get_weather(session)
        if not weather.empty:
            avg_air = weather["AirTemp"].mean()
            avg_track = weather["TrackTemp"].mean()
            rain = weather["Rainfall"].any()
            lines.append(f"## Weather")
            lines.append(f"Air: {avg_air:.1f}°C avg | Track: {avg_track:.1f}°C avg | Rain: {'Yes' if rain else 'No'}")
            lines.append("")
    except Exception:
        pass

    # Race control events
    try:
        rc = get_race_control(session)
        sc_events = rc[rc["Message"].str.contains("SAFETY CAR|VIRTUAL|RED FLAG", na=False, case=False)]
        if not sc_events.empty:
            lines.append("## Key Race Control Events")
            for _, e in sc_events.iterrows():
                lines.append(f"Lap {e['Lap']}: {e['Message']}")
            lines.append("")
    except Exception:
        pass

    # Stints summary
    try:
        stints = get_stints(session)
        lines.append("## Pit Stop Summary")
        for driver in stints["Driver"].unique()[:10]:
            d_stints = stints[stints["Driver"] == driver]
            compounds = d_stints.drop_duplicates("Stint")[["Stint", "Compound", "StartLap" if "StartLap" in d_stints.columns else "LapNumber"]].head()
            stint_str = " → ".join(
                f"{row['Compound']}@L{row.get('StartLap', row.get('LapNumber','?'))}"
                for _, row in d_stints.drop_duplicates("Stint").iterrows()
            )
            lines.append(f"{driver}: {stint_str}")
        lines.append("")
    except Exception:
        pass

    # Driver comparison if provided
    if driver_a and driver_b:
        try:
            lap_comp = get_lap_comparison(session, driver_a, driver_b)
            delta_avg = lap_comp["delta"].dropna().mean()
            faster = driver_a if delta_avg < 0 else driver_b
            lines.append(f"## {driver_a} vs {driver_b}")
            lines.append(f"Average lap delta: {abs(delta_avg):.3f}s — {faster} faster overall")
            for driver in [driver_a, driver_b]:
                c = get_consistency_score(session, driver)
                if c["std"] is not None:
                    lines.append(f"{driver} consistency: mean {c['mean']:.3f}s, std ±{c['std']:.3f}s over {c['n_laps']} clean laps")
            lines.append("")
        except Exception:
            pass

    return "\n".join(lines)


def ask_race_engineer(question: str, context: str, api_key: str):
    """Send question to Groq with race context. Returns streamed response."""
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
