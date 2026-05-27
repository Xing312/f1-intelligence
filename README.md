# F1 Race Intelligence Hub

**Live demo: https://f1-intelligence-da3qbujmtpszcne7xfrqfh.streamlit.app**

An interactive F1 race analytics platform built with real telemetry data. Select any race, dive into lap-level performance, tire strategy, and anomaly detection — or ask the AI race engineer directly.

## Features

| Page | What it shows |
|---|---|
| **Overview** | Race results, key metrics, weather timeline, track speed map |
| **Driver Duel** | Lap comparison, sector delta heatmap, telemetry overlay, track delta map |
| **Tire Strategy** | Full-field stint timeline, degradation regression, compound pace comparison |
| **Anomaly Detection** | Lap flagging by z-score, pit stops, safety car laps, and race control events |
| **AI Race Engineer** | Chat interface grounded in structured telemetry and race data |

## Tech Stack

| Layer | Tools |
|---|---|
| Data ingestion | FastF1, OpenF1 |
| Storage | DuckDB |
| Visualization | Plotly, Streamlit |
| ML / Analysis | scikit-learn, scipy |
| AI | Groq API (Llama 3.3 70B) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Data Pipeline                           │
│                                                                 │
│  FastF1 API ──► fetch_data.py ──► DuckDB (f1.duckdb)           │
│                      │            ├── race_results              │
│                      │            ├── lap_data                  │
│                      │            ├── weather_data              │
│                      │            ├── race_control              │
│                      └──► fetch_telemetry.py ──► telemetry      │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Analysis Layer                            │
│                                                                 │
│  src/pipeline/db.py        — all DuckDB queries                 │
│  src/analysis/lap_analysis.py   — lap deltas, consistency       │
│  src/analysis/tire_analysis.py  — stints, degradation           │
│  src/analysis/anomaly.py        — z-score flagging, SC laps     │
│  src/analysis/track_map.py      — Plotly circuit/delta maps     │
│  src/ai/race_engineer.py        — context builder + Groq chat   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Streamlit UI                              │
│                                                                 │
│  Home.py          — global session selector (year/round)        │
│  1_Overview.py    — results table, weather chart, speed map     │
│  2_Driver_Duel.py — lap compare, sector heatmap, delta map      │
│  3_Tire_Strategy.py — Gantt timeline, regression, pit window    │
│  4_Anomaly.py     — flagged lap scatter, event timeline         │
│  5_AI_Engineer.py — streaming chat grounded in race context     │
└─────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Pre-computed telemetry** — fastest-lap X/Y/Speed/Throttle for every driver is stored in DuckDB at ingest time, so circuit maps and driver telemetry overlays load instantly with no API calls at runtime.
- **DuckDB as the single source of truth** — all five pages read exclusively from `f1.duckdb`. No FastF1 imports at page load; no live API calls during user interaction.
- **Stateless pages** — `st.session_state` carries only the selected year/round/session. Every page is independently re-runnable; `importlib.reload()` is applied to all `src.*` modules so Streamlit Cloud never serves stale cached module bytecode.
- **Groq for AI** — Llama 3.3 70B via the Groq free-tier API. The race engineer builds a structured context string from DuckDB (results, stints, anomalies, weather) and injects it as the system prompt, keeping the LLM grounded in actual race data.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Fetch race data (downloads and caches sessions locally)
python src/pipeline/fetch_data.py 2024

# 3. Add your Groq API key
echo "GROQ_API_KEY=your_key_here" > .env

# 4. Launch
streamlit run streamlit_app/Home.py
```

## Project Structure

```
F1/
├── src/
│   ├── pipeline/        # Data fetching, session loading, DuckDB queries
│   ├── analysis/        # Lap analysis, tire strategy, anomaly detection, track maps
│   └── ai/              # AI race engineer (Groq API + race context builder)
├── streamlit_app/
│   ├── Home.py          # Landing page + global session selector
│   └── pages/           # One file per tab
├── notebooks/           # EDA and experimentation
└── data/                # Raw and processed data (git-ignored)
```

## Data

Sessions are fetched via FastF1 and persisted to DuckDB. Currently includes 2021–2025 full seasons (race results, lap times, weather, race control events, and fastest-lap telemetry for all drivers). Run the fetch scripts to add or update years:

```bash
python src/pipeline/fetch_data.py 2021 2022 2023 2024 2025
python src/pipeline/fetch_telemetry.py 2021 2022 2023 2024 2025
```

## Disclaimer

This project is unofficial and is not associated with Formula 1, Formula One Management (FOM), the FIA, or any F1 team. All F1-related data is sourced via [FastF1](https://github.com/theOehrly/Fast-F1), which accesses publicly available timing data. This project is intended for personal and educational use only and must not be used for commercial purposes.

AI-generated analysis from the Race Engineer feature is based on structured telemetry data and should not be taken as authoritative or official race commentary. Results may contain inaccuracies.
