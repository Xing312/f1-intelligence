# F1 Race Intelligence Hub

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

Sessions are fetched via FastF1 and cached locally. Currently includes 2024 full season race results and lap data. Run the fetch script with additional years as needed:

```bash
python src/pipeline/fetch_data.py 2022 2023 2024
```

## Disclaimer

This project is unofficial and is not associated with Formula 1, Formula One Management (FOM), the FIA, or any F1 team. All F1-related data is sourced via [FastF1](https://github.com/theOehrly/Fast-F1), which accesses publicly available timing data. This project is intended for personal and educational use only and must not be used for commercial purposes.

AI-generated analysis from the Race Engineer feature is based on structured telemetry data and should not be taken as authoritative or official race commentary. Results may contain inaccuracies.
