from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain

app = FastAPI(title="JARVIS OS")
brain = ProductBrain()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_HTML = BASE_DIR / "dashboard" / "jarvis_futuristic.html"


class ChatRequest(BaseModel):
    message: str
    domain: str | None = "general"


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    return {"status": "ok", "brain": brain.health()}


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/home")
def dashboard_home():
    return {
        "greeting": "JARVIS ready",
        "date": "Sunday 22 March 2026",
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
        result = brain.chat(req.message)

        return JSONResponse(
            content={
                "status": "ok",
                "response": result,
                "reply": result.get("reply", ""),
                "summary": result.get("summary", ""),
                "type": result.get("type", "chat"),
                "details": result.get("details", {}),
                "action": result.get("action", ""),
                "confidence": result.get("confidence", 0.0),
                "source": result.get("source", "brain"),
            },
            media_type="application/json; charset=utf-8"
        )

    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "response": {
                    "type": "error",
                    "reply": f"Error en chat: {e}",
                    "summary": f"Error en chat: {e}",
                    "details": {},
                    "action": "",
                    "confidence": 0.1,
                    "source": "main_chat_handler",
                },
            },
            media_type="application/json; charset=utf-8"
        )


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
        return {"items": [], "error": str(e)}


@app.get("/dashboard/assets")
def assets():
    return {"assets": []}


@app.post("/dashboard/tasks")
def add_task(data: dict):
    return {"status": "ok", "saved": data}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    return {"status": "ok", "task_id": task_id}


@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    return {"status": "ok", "saved": data}


@app.post("/dashboard/upload")
def upload_placeholder():
    return {"status": "ok"}
