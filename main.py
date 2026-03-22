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


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "dashboard_html_exists": DASHBOARD_HTML.exists(),
        "dashboard_html_path": str(DASHBOARD_HTML),
    }


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(
        status_code=404,
        detail=f"Dashboard not found at {DASHBOARD_HTML}"
    )


@app.get("/dashboard/home")
def dashboard_home():
    return {
        "greeting": "JARVIS ready",
        "date": datetime.utcnow().strftime("%A %d %B %Y"),
        "owner_name": "Juan Camilo",
        "top_priority": "Protect capital and increase asymmetric upside",
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
        payload = _safe_dict(result)

        reply = (
            payload.get("reply")
            or payload.get("summary")
            or payload.get("message")
            or "JARVIS procesó tu solicitud, pero no llegó una respuesta legible."
        )

        return {
            "status": "ok",
            "reply": reply,
            "summary": reply,
            "response": payload,
        }
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Chat error: {str(e)}",
            "summary": f"Chat error: {str(e)}",
            "response": {"error": str(e)},
        }


@app.post("/dashboard/trader")
def dashboard_trader(data: dict):
    try:
        symbol = (data or {}).get("symbol", "AAPL")
        result = brain.trader(symbol)
        payload = _safe_dict(result)

        return {
            "symbol": payload.get("symbol", str(symbol).upper()),
            "setup_score": payload.get("setup_score", "--"),
            "traffic_light": payload.get("traffic_light", "red"),
            "price_now": payload.get("price_now", payload.get("price", "--")),
            "summary": payload.get("summary", ""),
            "trade_plan": payload.get(
                "trade_plan",
                {
                    "action": payload.get("action", "-"),
                    "entry_zone": payload.get("entry_zone", []),
                    "stop_loss": payload.get("stop_loss", "-"),
                    "target_1": payload.get("target_1", "-"),
                    "target_2": payload.get("target_2", "-"),
                    "risk_reward_estimate": payload.get("risk_reward_estimate", "-"),
                },
            ),
            "insight_lines": payload.get(
                "insight_lines",
                payload.get("narrative", ["No insight available."]),
            ),
        }
    except Exception as e:
        return {
            "symbol": (data or {}).get("symbol", "AAPL"),
            "setup_score": "--",
            "traffic_light": "red",
            "price_now": "--",
            "summary": f"Trader error: {str(e)}",
            "trade_plan": {
                "action": "-",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "insight_lines": [f"Trader error: {str(e)}"],
        }


@app.get("/dashboard/recommendations")
def dashboard_recommendations():
    try:
        result = brain.recommendations()
        payload = _safe_dict(result)

        if isinstance(payload.get("items"), list):
            return payload

        if isinstance(result, list):
            return {"items": result}

        return {"items": []}
    except Exception as e:
        return {
            "items": [
                {
                    "symbol": "N/A",
                    "setup_score": "--",
                    "traffic_light": "red",
                    "friendly_recommendation": f"Recommendations error: {str(e)}",
                }
            ]
        }


@app.get("/dashboard/assets")
def dashboard_assets():
    return {"assets": []}


@app.post("/dashboard/tasks")
def add_task(data: dict):
    return {"status": "ok", "saved": True, "item": data}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    return {"status": "ok", "task_id": task_id}


@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    return {"status": "ok", "saved": True, "item": data}


@app.post("/dashboard/upload")
def dashboard_upload():
    return {"status": "ok"}
