from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain

app = FastAPI()
brain = ProductBrain()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_HTML = BASE_DIR / "dashboard" / "jarvis_futuristic.html"


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    try:
        brain_health = brain.health() if hasattr(brain, "health") else {"status": "unknown"}
    except Exception as e:
        brain_health = {"status": "error", "error": str(e)}

    return {
        "status": "ok",
        "brain": brain_health,
        "dashboard_html_exists": DASHBOARD_HTML.exists(),
        "dashboard_html": str(DASHBOARD_HTML),
    }


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/home")
def dashboard_home():
    return {
        "greeting": "JARVIS ready",
        "date": datetime.utcnow().strftime("%A %d %B %Y"),
        "owner_name": "Juan Camilo",
        "top_priority": "Protect capital",
        "tasks_open": 0,
        "assets_count": 0,
        "next_meeting": None,
        "tasks": [],
        "meetings": [],
    }


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        if hasattr(brain, "respond"):
            result = brain.respond(req.message)
        elif hasattr(brain, "chat"):
            result = brain.chat(req.message)
        else:
            raise Exception("ProductBrain has neither respond() nor chat()")

        return {
            "status": "ok",
            "response": result,
        }

    except Exception as e:
        return {
            "status": "error",
            "reply": f"Error en chat: {e}",
            "response": {},
        }


@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        symbol = data.get("symbol", "AAPL")
        return brain.trader(symbol)
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard/recommendations")
def recommendations():
    try:
        return brain.recommendations()
    except Exception as e:
        return {"error": str(e)}


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
