import os
import subprocess

mode = os.getenv("RUN_MODE", "api")

if mode == "dashboard":
    subprocess.run([
        "streamlit", "run", "dashboard/app.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])
else:
    subprocess.run([
        "uvicorn", "main:app",
        "--host", "0.0.0.0",
        "--port", os.getenv("PORT", "8000")
    ])
