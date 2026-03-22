from pathlib import Path
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain

app = FastAPI(title="JARVIS OS")
brain = ProductBrain()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DASHBOARD_HTML = DASHBOARD_DIR / "jarvis_futuristic.html"


class ChatRequest(BaseModel):
    message: str
    domain: str = "general"


def safe(value):
    return value if isinstance(value, dict) else {}


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


# =========================
# HOME
# =========================
@app.get("/dashboard/home")
def home():
    return {
        "greeting": "JARVIS ready",
        "date": datetime.utcnow().strftime("%A %d %B %Y"),
        "owner_name": "Juan Camilo",
        "top_priority": "Protect capital and compound asymmetric upside",
        "tasks_open": 0,
        "assets_count": 0,
        "next_meeting": None,
        "tasks": [],
        "meetings": [],
    }


# =========================
# CHAT (FIX REAL OUTPUT)
# =========================
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = brain.chat(req.message)
        payload = safe(result)

        reply = (
            payload.get("reply")
            or payload.get("summary")
            or payload.get("message")
            or str(payload)
        )

        return {
            "status": "ok",
            "reply": reply,
            "summary": reply,
            "raw": payload
        }

    except Exception as e:
        return {
            "status": "error",
            "reply": f"Error: {str(e)}"
        }


# =========================
# TRADER (PREMIUM OUTPUT)
# =========================
@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        symbol = data.get("symbol", "AAPL")
        result = brain.trader(symbol)
        payload = safe(result)

        return {
            "symbol": payload.get("symbol", symbol.upper()),
            "setup_score": payload.get("setup_score", payload.get("score", "--")),
            "traffic_light": payload.get("traffic_light", "yellow"),
            "price_now": payload.get("price_now", payload.get("price", "--")),
            "summary": payload.get("summary", ""),

            "trade_plan": payload.get("trade_plan", {
                "action": payload.get("action", "WAIT"),
                "entry_zone": payload.get("entry_zone", []),
                "stop_loss": payload.get("stop_loss", "-"),
                "target_1": payload.get("target_1", "-"),
                "target_2": payload.get("target_2", "-"),
                "risk_reward_estimate": payload.get("risk_reward_estimate", "-"),
            }),

            "insight_lines": payload.get(
                "insight_lines",
                payload.get("narrative", ["No insight available"])
            )
        }

    except Exception as e:
        return {
            "symbol": "ERROR",
            "setup_score": "--",
            "traffic_light": "red",
            "price_now": "--",
            "summary": str(e),
            "trade_plan": {},
            "insight_lines": [str(e)]
        }


# =========================
# RECOMMENDATIONS
# =========================
@app.get("/dashboard/recommendations")
def recommendations():
    try:
        result = brain.recommendations()
        if isinstance(result, list):
            return {"items": result}
        return result
    except:
        return {"items": []}


# =========================
# SAFE EMPTY ENDPOINTS
# =========================
@app.get("/dashboard/assets")
def assets():
    return {"assets": []}


@app.post("/dashboard/tasks")
def tasks(data: dict):
    return {"status": "ok"}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle(task_id: int):
    return {"status": "ok"}


@app.post("/dashboard/meetings")
def meetings(data: dict):
    return {"status": "ok"}


@app.post("/dashboard/upload")
def upload():
    return {"status": "ok"}
