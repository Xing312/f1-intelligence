import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

import streamlit as st
from dotenv import load_dotenv
from src.pipeline.db import get_drivers
from src.ai.race_engineer import build_race_context, ask_race_engineer

load_dotenv()

st.set_page_config(page_title="AI Race Engineer", page_icon="🤖", layout="wide")
st.title("🤖 AI Race Engineer")
st.markdown("Ask questions about this race — answers are grounded in race data.")

year = st.session_state.get("year", 2024)
round_num = st.session_state.get("round_num", 1)
event_name = st.session_state.get("event_name", "")
st.caption(f"{event_name} · {year}")

api_key = os.getenv("GROQ_API_KEY", "") or st.secrets.get("GROQ_API_KEY", "")
if not api_key:
    st.error("GROQ_API_KEY not found. Add it to `.env` or Streamlit secrets.")
    st.stop()

drivers = get_drivers(year, round_num)

with st.expander("Add driver comparison context (optional)"):
    col1, col2 = st.columns(2)
    with col1:
        driver_a = st.selectbox("Driver A", ["—"] + drivers)
    with col2:
        driver_b = st.selectbox("Driver B", ["—"] + drivers)
    da = driver_a if driver_a != "—" else None
    db_drv = driver_b if driver_b != "—" else None


@st.cache_data(show_spinner="Building race context…")
def get_context(yr, rnd, da, db_drv):
    return build_race_context(yr, rnd, da, db_drv)


context = get_context(year, round_num, da, db_drv)

with st.expander("Race Data Context (sent to AI)"):
    st.code(context, language="markdown")

st.divider()

suggestions = [
    "Who had the best race pace overall?",
    "Was there an effective undercut strategy used?",
    "Which driver managed their tyres best?",
    "What impact did the Safety Car have on the race?",
    "Who made the biggest positions gained from grid to finish?",
]
st.markdown("**Suggested questions:**")
cols = st.columns(len(suggestions))
for i, q in enumerate(suggestions):
    if cols[i].button(q, key=f"suggest_{i}"):
        st.session_state["prefill"] = q

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
