import streamlit as st
import requests
import os

# 🔥 CONFIG DINÁMICA (LOCAL vs PRODUCCIÓN)
BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="JARVIS Control Room", layout="wide")

st.title("JARVIS Control Room")
st.caption("Juan Camilo Montenegro | Personal Strategic Intelligence System")

st.write(f"🔗 Connected to: {BASE}")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Health"):
        try:
            res = requests.get(f"{BASE}/health")
            st.json(res.json())
        except Exception as e:
            st.error(f"Error: {e}")

with col2:
    if st.button("Automation Status"):
        try:
            res = requests.get(f"{BASE}/automation/status")
            st.json(res.json())
        except Exception as e:
            st.error(f"Error: {e}")

with col3:
    if st.button("Audit Events"):
        try:
            res = requests.get(f"{BASE}/audit/events")
            st.json(res.json())
        except Exception as e:
            st.error(f"Error: {e}")

st.subheader("Premium Council")

topic = st.text_input(
    "Council topic",
    "Should I increase oil exposure if middle east tensions escalate?"
)

domain = st.selectbox(
    "Domain",
    ["general", "finance", "investment", "macro", "wealth", "health", "life"]
)

if st.button("Run Council"):
    try:
        payload = {
            "topic": topic,
            "domain": domain,
            "owner_name": "Juan Camilo Montenegro"
        }
        res = requests.post(f"{BASE}/premium/council", json=payload)
        st.json(res.json())
    except Exception as e:
        st.error(f"Error: {e}")

st.subheader("Geopolitical Intelligence")

geo_topic = st.text_input("Geo topic", "oil war middle east")
geo_context = st.text_input("Geo context", "iran israel escalation")

if st.button("Run Geopolitical Intelligence"):
    try:
        payload = {
            "topic": geo_topic,
            "context": geo_context
        }
        res = requests.post(f"{BASE}/premium/geopolitical", json=payload)
        st.json(res.json())
    except Exception as e:
        st.error(f"Error: {e}")

st.subheader("Voice Natural")

voice_text = st.text_area(
    "Text to synthesize",
    "Welcome Juan Camilo Montenegro. JARVIS is online."
)

if st.button("Synthesize Voice"):
    try:
        payload = {
            "text": voice_text,
            "provider": "elevenlabs",
            "style": "natural executive"
        }
        res = requests.post(f"{BASE}/premium/voice/synthesize", json=payload)
        st.json(res.json())
    except Exception as e:
        st.error(f"Error: {e}")