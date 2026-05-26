import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
from dotenv import load_dotenv
from src.pipeline.session_loader import load_session
from src.ai.race_engineer import build_race_context, ask_race_engineer

load_dotenv()

st.set_page_config(page_title="AI Race Engineer", page_icon="🤖", layout="wide")
st.title("🤖 AI Race Engineer")
st.markdown("Ask questions about this race — answers are grounded in telemetry and race data.")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
session_code = st.session_state.get("session_code", "R")
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")

api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")
if not api_key:
    st.error("GROQ_API_KEY not found. Add it to `.env` or Streamlit secrets.")
    st.stop()


@st.cache_resource(show_spinner="Loading session data…")
def load(yr, rnd, sc):
    return load_session(yr, rnd, sc)


session = load(year, round_num, session_code)

# Optional driver context
drivers = session.results["Abbreviation"].tolist()
with st.expander("Add driver comparison context (optional)"):
    col1, col2 = st.columns(2)
    with col1:
        driver_a = st.selectbox("Driver A", ["—"] + drivers)
    with col2:
        driver_b = st.selectbox("Driver B", ["—"] + drivers)
    da = driver_a if driver_a != "—" else None
    db = driver_b if driver_b != "—" else None

# Build context once per session selection
@st.cache_data(show_spinner="Building race context…")
def get_context(yr, rnd, sc, da, db):
    sess = load(yr, rnd, sc)
    return build_race_context(sess, da, db)

context = get_context(year, round_num, session_code, da, db)

with st.expander("Race Data Context (sent to AI)"):
    st.code(context, language="markdown")

st.divider()

# Suggested questions
st.markdown("**Suggested questions:**")
suggestions = [
    "Who had the best race pace overall?",
    "Was there an effective undercut strategy used?",
    "Which driver managed their tyres best?",
    "What impact did the Safety Car have on the race?",
    "Who made the biggest positions gained from grid to finish?",
]
cols = st.columns(len(suggestions))
for i, q in enumerate(suggestions):
    if cols[i].button(q, key=f"suggest_{i}"):
        st.session_state["prefill"] = q

# Chat history
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
prefill = st.session_state.pop("prefill", "")
question = st.chat_input("Ask about this race…") or prefill

if question:
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = ""
        try:
            for chunk in ask_race_engineer(question, context, api_key):
                response += chunk
                placeholder.markdown(response + "▌")
            placeholder.markdown(response)
        except Exception as e:
            response = f"Error: {e}"
            placeholder.markdown(response)

    st.session_state["chat_history"].append({"role": "assistant", "content": response})

if st.button("Clear chat"):
    st.session_state["chat_history"] = []
    st.rerun()
