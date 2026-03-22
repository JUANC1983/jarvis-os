from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime

from core.product_brain import ProductBrain

app = FastAPI()
brain = ProductBrain()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DASHBOARD_HTML = DASHBOARD_DIR / "jarvis_futuristic.html"


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/home")
def home():
    return {
        "greeting": "JARVIS ready",
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "owner_name": "Juan Camilo",
        "top_priority": "Protect capital",
        "tasks_open": 0,
        "assets_count": 0,
        "next_meeting": None,
        "tasks": [],
        "meetings": []
    }


@app.post("/chat")
def chat(req: ChatRequest):
    result = brain.chat(req.message)

    return {
        "status": "ok",
        "response": result
    }


@app.post("/dashboard/trader")
def trader(data: dict):
    return brain.trader(data.get("symbol", "AAPL"))


@app.get("/dashboard/recommendations")
def recommendations():
    return brain.recommendations()


@app.get("/dashboard/assets")
def assets():
    return {"assets": []}


@app.post("/dashboard/tasks")
def add_task(data: dict):
    return {"status": "ok"}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    return {"status": "ok"}


@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    return {"status": "ok"}
