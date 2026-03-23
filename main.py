from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# =========================
# SAFE PRODUCT BRAIN IMPORT
# =========================
_PRODUCT_BRAIN_CLASS = None
_PRODUCT_BRAIN_IMPORT_ERROR = None

try:
    from core.product_brain import ProductBrain as _ImportedProductBrain
    _PRODUCT_BRAIN_CLASS = _ImportedProductBrain
except Exception as e:
    _PRODUCT_BRAIN_IMPORT_ERROR = str(e)


app = FastAPI(title="JARVIS OS")

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_HTML = BASE_DIR / "dashboard" / "jarvis_futuristic.html"
MEMORY_DIR = BASE_DIR / "memory"
UPLOADS_DIR = BASE_DIR / "uploads"
TASKS_FILE = MEMORY_DIR / "dashboard_tasks.json"
MEETINGS_FILE = MEMORY_DIR / "dashboard_meetings.json"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

brain = None
boot_errors: list[str] = []


# =========================
# SAFE BOOT
# =========================
def _boot_brain() -> None:
    global brain

    if brain is not None:
        return

    if _PRODUCT_BRAIN_CLASS is None:
        if _PRODUCT_BRAIN_IMPORT_ERROR and _PRODUCT_BRAIN_IMPORT_ERROR not in boot_errors:
            boot_errors.append(f"ProductBrain import error: {_PRODUCT_BRAIN_IMPORT_ERROR}")
        return

    try:
        brain = _PRODUCT_BRAIN_CLASS()
    except Exception as e:
        msg = f"ProductBrain init error: {e}"
        if msg not in boot_errors:
            boot_errors.append(msg)
        brain = None


_boot_brain()


# =========================
# JSON STORAGE HELPERS
# =========================
def _read_json_file(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json_file(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_tasks() -> list[dict]:
    data = _read_json_file(TASKS_FILE, [])
    return data if isinstance(data, list) else []


def _save_tasks(tasks: list[dict]) -> None:
    _write_json_file(TASKS_FILE, tasks)


def _get_meetings() -> list[dict]:
    data = _read_json_file(MEETINGS_FILE, [])
    return data if isinstance(data, list) else []


def _save_meetings(meetings: list[dict]) -> None:
    _write_json_file(MEETINGS_FILE, meetings)


def _next_id(items: list[dict]) -> int:
    if not items:
        return 1
    return max(int(item.get("id", 0)) for item in items) + 1


# =========================
# BRAIN HELPERS
# =========================
def _brain_health() -> dict:
    if brain is None:
        return {
            "available": False,
            "boot_errors": boot_errors,
            "orchestrator_available": False,
        }

    try:
        health = brain.health()
        if isinstance(health, dict):
            if "boot_errors" not in health:
                health["boot_errors"] = boot_errors
            return health
    except Exception as e:
        return {
            "available": False,
            "boot_errors": boot_errors + [f"health error: {e}"],
            "orchestrator_available": False,
        }

    return {
        "available": True,
        "boot_errors": boot_errors,
        "orchestrator_available": True,
    }


def _normalize_chat_result(result: Any) -> dict:
    if isinstance(result, str):
        return {
            "type": "chat",
            "reply": result,
            "summary": result,
            "details": {},
            "action": "",
            "confidence": 0.7,
            "source": "product_brain_string",
        }

    if not isinstance(result, dict):
        text = str(result)
        return {
            "type": "chat",
            "reply": text,
            "summary": text,
            "details": {},
            "action": "",
            "confidence": 0.5,
            "source": "product_brain_unknown",
        }

    reply = result.get("reply") or result.get("summary") or "JARVIS recibió tu mensaje."
    result.setdefault("type", "chat")
    result.setdefault("reply", reply)
    result.setdefault("summary", reply)
    result.setdefault("details", {})
    result.setdefault("action", "")
    result.setdefault("confidence", 0.6)
    result.setdefault("source", "product_brain")
    return result


def _normalize_recommendations(result: Any) -> dict:
    if isinstance(result, dict) and "items" in result:
        items = result.get("items") or []
        return {"items": items}

    if isinstance(result, list):
        return {"items": result}

    if isinstance(result, dict):
        return {"items": [result]}

    return {"items": []}


# =========================
# ROOT / HEALTH
# =========================
@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    _boot_brain()
    return {"status": "ok", "brain": _brain_health()}


@app.get("/favicon.ico")
def favicon():
    return JSONResponse(status_code=204, content=None)


# =========================
# DASHBOARD HTML
# =========================
@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get("/dashboard/home")
def dashboard_home():
    tasks = _get_tasks()
    meetings = _get_meetings()

    open_tasks = [t for t in tasks if not t.get("done")]
    pending_meetings = sorted(
        meetings,
        key=lambda x: str(x.get("time", "99:99"))
    )

    next_meeting = pending_meetings[0] if pending_meetings else None

    top_priority = "Protect capital"
    if open_tasks:
        top_priority = open_tasks[0].get("text", "Protect capital")

    return {
        "greeting": "JARVIS ready",
        "date": datetime.now().strftime("%A %d %B %Y"),
        "owner_name": "Juan Camilo",
        "top_priority": top_priority,
        "tasks_open": len(open_tasks),
        "assets_count": len(list(UPLOADS_DIR.glob("*"))),
        "next_meeting": next_meeting,
        "tasks": tasks,
        "meetings": meetings,
    }


# =========================
# CHAT
# =========================
@app.get("/chat")
def chat_info():
    return {
        "status": "ok",
        "message": "Use POST /chat with JSON body: {\"message\": \"...\"}"
    }


@app.post("/chat")
def chat(data: dict):
    _boot_brain()

    message = str(data.get("message", "")).strip()
    if not message:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "response": {
                    "type": "error",
                    "reply": "Falta el campo 'message'.",
                    "summary": "Falta el campo 'message'.",
                    "details": {},
                    "action": "",
                    "confidence": 0.1,
                    "source": "main_chat_handler",
                },
                "reply": "Falta el campo 'message'.",
                "summary": "Falta el campo 'message'.",
            },
        )

    if brain is None:
        fallback = {
            "type": "error",
            "reply": "JARVIS está online, pero el brain no está disponible todavía.",
            "summary": "JARVIS está online, pero el brain no está disponible todavía.",
            "details": {"boot_errors": boot_errors},
            "action": "",
            "confidence": 0.1,
            "source": "main_chat_handler",
        }
        return {
            "status": "error",
            "response": fallback,
            "reply": fallback["reply"],
            "summary": fallback["summary"],
        }

    try:
        if hasattr(brain, "chat"):
            result = brain.chat(message)
        elif hasattr(brain, "respond"):
            result = brain.respond(message)
        else:
            result = {
                "type": "chat",
                "reply": f"JARVIS recibió: {message}",
                "summary": f"JARVIS recibió: {message}",
                "details": {},
                "action": "",
                "confidence": 0.5,
                "source": "main_chat_fallback",
            }

        normalized = _normalize_chat_result(result)

        # compatibilidad con frontend viejo y nuevo
        return {
            "status": "ok",
            "response": normalized,
            "reply": normalized["reply"],
            "summary": normalized["summary"],
            "type": normalized["type"],
            "details": normalized["details"],
            "action": normalized["action"],
            "confidence": normalized["confidence"],
            "source": normalized["source"],
        }

    except Exception as e:
        error_payload = {
            "type": "error",
            "reply": f"Error en chat: {e}",
            "summary": f"Error en chat: {e}",
            "details": {},
            "action": "",
            "confidence": 0.1,
            "source": "main_chat_handler",
        }
        return {
            "status": "error",
            "response": error_payload,
            "reply": error_payload["reply"],
            "summary": error_payload["summary"],
        }


# =========================
# TRADER
# =========================
@app.post("/dashboard/trader")
def trader(data: dict):
    _boot_brain()

    try:
        symbol = str(data.get("symbol", "AAPL")).strip() or "AAPL"

        if brain is None:
            return {
                "symbol": symbol.upper(),
                "price": None,
                "price_now": None,
                "setup_score": 50,
                "traffic_light": "yellow",
                "trade_plan": {
                    "action": "WAIT",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-",
                },
                "insight_lines": ["Brain no disponible todavía."],
                "summary": "Brain no disponible todavía.",
                "friendly_recommendation": "No hay contexto suficiente todavía.",
                "source": "main_trader_fallback",
            }

        if hasattr(brain, "trader"):
            result = brain.trader(symbol)
        elif hasattr(brain, "analyze_symbol"):
            result = brain.analyze_symbol(symbol)
        else:
            raise RuntimeError("Brain has no trader/analyze_symbol method")

        if not isinstance(result, dict):
            raise RuntimeError("Trader response is not a dict")

        return result

    except Exception as e:
        return {
            "symbol": str(data.get("symbol", "AAPL")).upper(),
            "price": None,
            "price_now": None,
            "setup_score": 50,
            "traffic_light": "yellow",
            "trade_plan": {
                "action": "WAIT",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "insight_lines": [f"Error trader: {e}"],
            "summary": f"Error trader: {e}",
            "friendly_recommendation": "No se pudo generar análisis ahora.",
            "source": "main_trader_handler",
        }


# =========================
# RECOMMENDATIONS
# =========================
@app.get("/dashboard/recommendations")
def recommendations():
    _boot_brain()

    try:
        if brain is None:
            return {"items": [], "error": "brain not available"}

        if hasattr(brain, "recommendations"):
            result = brain.recommendations()
        elif hasattr(brain, "get_recommendations"):
            result = brain.get_recommendations()
        else:
            result = {"items": []}

        return _normalize_recommendations(result)

    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# ASSETS / UPLOADS
# =========================
@app.get("/dashboard/assets")
def assets():
    items = []
    for path in sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_file():
            items.append({
                "filename": path.name,
                "kind": "file",
                "mime_type": "",
            })
    return {"assets": items}


@app.post("/dashboard/upload")
def upload_placeholder(file: UploadFile = File(...)):
    destination = UPLOADS_DIR / Path(file.filename).name
    destination.write_bytes(file.file.read())
    return {"status": "ok", "filename": destination.name}


@app.get("/dashboard/uploads/{filename}")
def get_uploaded_file(filename: str):
    safe_path = (UPLOADS_DIR / filename).resolve()
    if not str(safe_path).startswith(str(UPLOADS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(safe_path)


# =========================
# TASKS
# =========================
@app.post("/dashboard/tasks")
def add_task(data: dict):
    tasks = _get_tasks()

    text = str(data.get("text", "")).strip()
    priority = str(data.get("priority", "medium")).strip() or "medium"
    day = str(data.get("day", "today")).strip() or "today"

    if not text:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Task text required"})

    task = {
        "id": _next_id(tasks),
        "text": text,
        "priority": priority,
        "day": day,
        "done": False,
        "created_at": datetime.now().isoformat(),
    }

    tasks.append(task)
    _save_tasks(tasks)
    return {"status": "ok", "saved": task}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    tasks = _get_tasks()
    updated = None

    for task in tasks:
        if int(task.get("id", 0)) == task_id:
            task["done"] = not bool(task.get("done", False))
            updated = task
            break

    _save_tasks(tasks)
    return {"status": "ok", "task": updated, "task_id": task_id}


# =========================
# MEETINGS
# =========================
@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    meetings = _get_meetings()

    title = str(data.get("title", "")).strip()
    time_value = str(data.get("time", "")).strip()
    notes = str(data.get("notes", "")).strip()

    if not title or not time_value:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Meeting title and time required"})

    meeting = {
        "id": _next_id(meetings),
        "title": title,
        "time": time_value,
        "notes": notes,
        "created_at": datetime.now().isoformat(),
    }

    meetings.append(meeting)
    meetings = sorted(meetings, key=lambda x: str(x.get("time", "99:99")))
    _save_meetings(meetings)

    return {"status": "ok", "saved": meeting}


# =========================
# AUTO MODE
# =========================
@app.post("/jarvis/auto")
def auto_jarvis():
    return {
        "status": "ok",
        "reply": "Auto JARVIS ejecutado en modo seguro. No se envían órdenes sin consentimiento.",
        "summary": "Auto JARVIS ejecutado en modo seguro."
    }
