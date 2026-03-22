from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List
import math

from fastapi import FastAPI, HTTPException, UploadFile, File
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


TASKS: List[Dict[str, Any]] = []
MEETINGS: List[Dict[str, Any]] = []
ASSETS: List[Dict[str, Any]] = []


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def score_to_light(score: Any) -> str:
    try:
        s = float(score)
    except Exception:
        return "yellow"
    if s >= 80:
        return "green"
    if s >= 60:
        return "yellow"
    return "red"


def friendly_action(light: str, score: Any) -> str:
    if light == "green":
        return "GO"
    if light == "yellow":
        return "WAIT"
    return "AVOID"


def normalize_price(value: Any) -> Any:
    if value is None or value == "":
        return "--"
    try:
        return round(float(value), 2)
    except Exception:
        return value


def build_insight_lines(symbol: str, price_now: Any, score: Any, action: str, raw: Dict[str, Any]) -> List[str]:
    lines = raw.get("insight_lines")
    if isinstance(lines, list) and lines:
        return [str(x) for x in lines if str(x).strip()]

    narrative = raw.get("narrative")
    if isinstance(narrative, list) and narrative:
        return [str(x) for x in narrative if str(x).strip()]
    if isinstance(narrative, str) and narrative.strip():
        return [narrative.strip()]

    summary = raw.get("summary")
    if isinstance(summary, str) and summary.strip():
        return [summary.strip()]

    try:
        s = float(score)
    except Exception:
        s = None

    if s is None:
        return [f"{symbol}: sin suficiente contexto todavía."]

    if s >= 80:
        return [f"{symbol}: setup fuerte. Solo entrar si confirma y con riesgo controlado."]
    if s >= 60:
        return [f"{symbol}: setup aceptable. Mejor esperar una entrada más limpia."]
    return [f"{symbol}: no hay ventaja clara ahora. Mejor no entrar."]


def build_trade_plan(symbol: str, price_now: Any, score: Any, raw: Dict[str, Any]) -> Dict[str, Any]:
    existing = raw.get("trade_plan")
    if isinstance(existing, dict) and existing:
        return {
            "action": existing.get("action", raw.get("action", "WAIT")),
            "entry_zone": existing.get("entry_zone", []),
            "stop_loss": existing.get("stop_loss", "-"),
            "target_1": existing.get("target_1", "-"),
            "target_2": existing.get("target_2", "-"),
            "risk_reward_estimate": existing.get("risk_reward_estimate", "-"),
        }

    try:
        p = float(price_now)
        s = float(score)
    except Exception:
        return {
            "action": raw.get("action", "WAIT"),
            "entry_zone": [],
            "stop_loss": "-",
            "target_1": "-",
            "target_2": "-",
            "risk_reward_estimate": "-",
        }

    volatility = 0.018 if p > 500 else 0.022
    entry_low = round(p * (1 - volatility), 2)
    entry_high = round(p * (1 + volatility * 0.4), 2)
    stop_loss = round(p * (1 - volatility * 2), 2)
    target_1 = round(p * (1 + volatility * 1.4), 2)
    target_2 = round(p * (1 + volatility * 3), 2)

    risk = max(p - stop_loss, 0.01)
    reward = max(target_1 - p, 0.01)
    rr = round(reward / risk, 2)

    action = "WAIT"
    if s >= 80:
        action = "GO"
    elif s >= 60:
        action = "WAIT"
    else:
        action = "AVOID"

    return {
        "action": action,
        "entry_zone": [entry_low, entry_high],
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "risk_reward_estimate": rr,
    }


def normalize_trader_result(symbol: str, raw: Any) -> Dict[str, Any]:
    payload = as_dict(raw)

    score = payload.get("setup_score", payload.get("score", "--"))
    light = payload.get("traffic_light", payload.get("light", score_to_light(score)))
    price_now = normalize_price(payload.get("price_now", payload.get("price", payload.get("last_price"))))
    trade_plan = build_trade_plan(symbol, price_now, score, payload)
    insight_lines = build_insight_lines(symbol, price_now, score, trade_plan.get("action", "WAIT"), payload)

    return {
        "symbol": str(payload.get("symbol", symbol)).upper(),
        "setup_score": score,
        "traffic_light": light,
        "price_now": price_now,
        "summary": payload.get("summary", insight_lines[0] if insight_lines else ""),
        "trade_plan": trade_plan,
        "insight_lines": insight_lines,
    }


def normalize_chat_result(raw: Any) -> Dict[str, Any]:
    payload = as_dict(raw)

    reply = (
        payload.get("reply")
        or payload.get("summary")
        or payload.get("message")
        or payload.get("answer")
        or payload.get("content")
    )

    if not reply and isinstance(raw, str):
        reply = raw

    if not reply:
        reply = "Sistema estable. Pregunta por oportunidades específicas."

    return {
        "status": "ok",
        "reply": str(reply),
        "response": payload,
    }


def build_recommendations_from_trader() -> Dict[str, Any]:
    tickers = ["NVDA", "AAPL", "MSFT", "ASML"]
    items = []

    for symbol in tickers:
        try:
            raw = brain.trader(symbol)
            n = normalize_trader_result(symbol, raw)
            items.append({
                "symbol": n["symbol"],
                "setup_score": n["setup_score"],
                "traffic_light": n["traffic_light"],
                "friendly_recommendation": n["insight_lines"][0] if n["insight_lines"] else f"{symbol}: sin comentario disponible.",
            })
        except Exception:
            continue

    def sort_key(x: Dict[str, Any]) -> float:
        try:
            return float(x.get("setup_score", 0))
        except Exception:
            return 0.0

    items = sorted(items, key=sort_key, reverse=True)
    return {"items": items}


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "jarvis-os"}


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/home")
def home():
    tasks_open = sum(1 for t in TASKS if not t.get("done", False))
    next_meeting = None
    if MEETINGS:
        next_meeting = MEETINGS[0]

    top_priority = "Protect capital"
    try:
        recs = build_recommendations_from_trader().get("items", [])
        if recs:
            best = recs[0]
            symbol = best.get("symbol", "N/A")
            score = best.get("setup_score", "--")
            top_priority = f"Review {symbol} setup ({score})"
    except Exception:
        pass

    return {
        "greeting": "JARVIS ready",
        "date": datetime.utcnow().strftime("%A %d %B %Y"),
        "owner_name": "Juan Camilo",
        "top_priority": top_priority,
        "tasks_open": tasks_open,
        "assets_count": len(ASSETS),
        "next_meeting": next_meeting,
        "tasks": TASKS,
        "meetings": MEETINGS,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = brain.chat(req.message)
        return normalize_chat_result(result)
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Error en chat: {str(e)}",
            "response": {},
        }


@app.post("/dashboard/trader")
def trader(data: dict):
    symbol = str(data.get("symbol", "AAPL")).strip().upper() or "AAPL"
    try:
        result = brain.trader(symbol)
        return normalize_trader_result(symbol, result)
    except Exception as e:
        return {
            "symbol": symbol,
            "setup_score": "--",
            "traffic_light": "red",
            "price_now": "--",
            "summary": str(e),
            "trade_plan": {
                "action": "AVOID",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "insight_lines": [f"{symbol}: error obteniendo análisis."],
        }


@app.get("/dashboard/recommendations")
def recommendations():
    try:
        result = brain.recommendations()
        if isinstance(result, dict):
            items = result.get("items")
            if isinstance(items, list) and items:
                return result
        if isinstance(result, list) and result:
            return {"items": result}
    except Exception:
        pass

    return build_recommendations_from_trader()


@app.get("/dashboard/assets")
def assets():
    return {"assets": ASSETS}


@app.post("/dashboard/tasks")
def add_task(data: dict):
    text = str(data.get("text", "")).strip()
    if not text:
        return {"status": "error", "message": "Task text required"}

    task = {
        "id": len(TASKS) + 1,
        "text": text,
        "priority": data.get("priority", "medium"),
        "day": data.get("day", "today"),
        "done": False,
    }
    TASKS.append(task)
    return {"status": "ok", "task": task}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    for task in TASKS:
        if task["id"] == task_id:
            task["done"] = not task.get("done", False)
            return {"status": "ok", "task": task}
    return {"status": "error", "message": "Task not found"}


@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    title = str(data.get("title", "")).strip()
    time_value = str(data.get("time", "")).strip()
    notes = str(data.get("notes", "")).strip()

    if not title or not time_value:
        return {"status": "error", "message": "Meeting title and time required"}

    meeting = {
        "id": len(MEETINGS) + 1,
        "title": title,
        "time": time_value,
        "notes": notes,
    }
    MEETINGS.append(meeting)
    return {"status": "ok", "meeting": meeting}


@app.post("/dashboard/upload")
async def dashboard_upload(file: UploadFile = File(...)):
    ASSETS.append({
        "filename": file.filename,
        "kind": "file",
        "mime_type": file.content_type or "application/octet-stream",
    })
    return {"status": "ok", "filename": file.filename}


@app.post("/jarvis/auto")
def jarvis_auto():
    try:
        recs = build_recommendations_from_trader().get("items", [])
        if recs:
            top = recs[0]
            symbol = top.get("symbol", "N/A")
            score = top.get("setup_score", "--")
            return {
                "status": "ok",
                "reply": f"Modo auto seguro listo. Prioridad actual: revisar {symbol} con score {score}. No ejecutar compras ni ventas sin confirmación manual."
            }
    except Exception:
        pass

    return {
        "status": "ok",
        "reply": "Modo auto seguro activado. Seguimiento solamente, sin ejecutar compras ni ventas."
    }
