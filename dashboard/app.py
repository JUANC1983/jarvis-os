import streamlit as st
import requests

BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="JARVIS Control Room", layout="wide")

st.title("JARVIS Control Room")
st.caption("Juan Camilo Montenegro | Personal Strategic Intelligence System")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Health"):
        st.json(requests.get(f"{BASE}/health").json())

with col2:
    if st.button("Automation Status"):
        st.json(requests.get(f"{BASE}/automation/status").json())

with col3:
    if st.button("Audit Events"):
        st.json(requests.get(f"{BASE}/audit/events").json())

st.subheader("Premium Council")
topic = st.text_input("Council topic", "Should I increase oil exposure if middle east tensions escalate?")
domain = st.selectbox("Domain", ["general", "finance", "investment", "macro", "wealth", "health", "life"])

if st.button("Run Council"):
    payload = {"topic": topic, "domain": domain, "owner_name": "Juan Camilo Montenegro"}
    st.json(requests.post(f"{BASE}/premium/council", json=payload).json())

st.subheader("Geopolitical Intelligence")
geo_topic = st.text_input("Geo topic", "oil war middle east")
geo_context = st.text_input("Geo context", "iran israel escalation")

if st.button("Run Geopolitical Intelligence"):
    payload = {"topic": geo_topic, "context": geo_context}
    st.json(requests.post(f"{BASE}/premium/geopolitical", json=payload).json())

st.subheader("Voice Natural")
voice_text = st.text_area("Text to synthesize", "Welcome Juan Camilo Montenegro. JARVIS is online.")

if st.button("Synthesize Voice"):
    payload = {"text": voice_text, "provider": "elevenlabs", "style": "natural executive"}
    st.json(requests.post(f"{BASE}/premium/voice/synthesize", json=payload).json())
