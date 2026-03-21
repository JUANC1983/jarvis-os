import os
from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def root():
    return {"status": "JARVIS OS RUNNING"}

@app.get("/dashboard")
def dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard/jarvis_futuristic.html"))
