import json
import os
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.jarvis_os import JarvisOS

app = FastAPI(title="JARVIS OS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
UPLOAD_DIR = os.path.join(DASHBOARD_DIR, "uploads")
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
MEETINGS_FILE = os.path.join(DATA_DIR, "meetings.json")
ASSETS_FILE = os.path.join(DATA_DIR, "assets.json")

jarvis = JarvisOS()


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if os.path.isdir(UPLOAD_DIR):
    app.mount("/dashboard/uploads", StaticFiles(directory=UPLOAD_DIR), name="dashboard_uploads")


@app.get("/")
def root():
    return {
        "status": "JARVIS OS RUNNING",
        "health": jarvis.health(),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "jarvis_loaded": jarvis is not None,
        "jarvis_health": jarvis.health(),
    }


@app.get("/dashboard")
def dashboard():
    dashboard_file = os.path.join(DASHBOARD_DIR, "jarvis_futuristic.html")
    if os.path.exists(dashboard_file):
        return FileResponse(dashboard_file)
    return JSONResponse({"ok": False, "error": "dashboard/jarvis_futuristic.html not found"}, status_code=404)


@app.get("/docs-check")
def docs_check():
    return {"ok": True, "message": "Swagger docs should be available at /docs"}


@app.get("/dashboard/home")
def dashboard_home():
    tasks = load_json(TASKS_FILE, [])
    meetings = load_json(MEETINGS_FILE, [])
    assets = load_json(ASSETS_FILE, [])

    next_meeting = meetings[0] if meetings else None

    return {
        "greeting": "JARVIS ready",
        "date": "Today",
        "owner_name": "Juan Camilo",
        "top_priority": "Protect capital and increase intelligent opportunities",
        "tasks_open": len([t for t in tasks if not t.get("done")]),
        "assets_count": len(assets),
        "tasks": tasks,
        "meetings": meetings,
        "next_meeting": next_meeting,
    }


@app.post("/chat")
async def chat(payload: Dict[str, Any]):
    message = str(payload.get("message", "")).strip()

    if not message:
        return JSONResponse(
            {
                "type": "general",
                "summary": "Escribe un mensaje primero.",
                "details": {},
                "action": "Try again with a specific request.",
                "confidence": 0.0,
                "source": "validation",
            },
            status_code=400,
        )

    result = jarvis.chat(message)
    return result


@app.post("/dashboard/tasks")
def add_task(payload: Dict[str, Any]):
    tasks = load_json(TASKS_FILE, [])

    task = {
        "id": len(tasks) + 1,
        "text": str(payload.get("text", "")).strip(),
        "priority": str(payload.get("priority", "medium")).strip() or "medium",
        "day": str(payload.get("day", "today")).strip() or "today",
        "done": False,
    }

    if not task["text"]:
        return JSONResponse({"ok": False, "error": "Task text is required"}, status_code=400)

    tasks.append(task)
    save_json(TASKS_FILE, tasks)
    return {"ok": True, "task": task}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    tasks = load_json(TASKS_FILE, [])
    found = False

    for task in tasks:
        if task.get("id") == task_id:
            task["done"] = not task.get("done", False)
            found = True
            break

    save_json(TASKS_FILE, tasks)
    return {"ok": found}


@app.post("/dashboard/meetings")
def add_meeting(payload: Dict[str, Any]):
    meetings = load_json(MEETINGS_FILE, [])

    item = {
        "title": str(payload.get("title", "")).strip(),
        "time": str(payload.get("time", "")).strip(),
        "notes": str(payload.get("notes", "")).strip(),
    }

    if not item["title"] or not item["time"]:
        return JSONResponse({"ok": False, "error": "Meeting title and time are required"}, status_code=400)

    meetings.append(item)
    save_json(MEETINGS_FILE, meetings)
    return {"ok": True, "meeting": item}


@app.post("/dashboard/trader")
def dashboard_trader(payload: Dict[str, Any]):
    symbol = str(payload.get("symbol", "AAPL")).strip() or "AAPL"
    return jarvis.trader(symbol)


@app.get("/dashboard/recommendations")
def dashboard_recommendations():
    return {
        "items": [
            {
                "symbol": "AAPL",
                "setup_score": 8,
                "traffic_light": "green",
                "summary": "High quality structure with favorable institutional profile.",
            },
            {
                "symbol": "NVDA",
                "setup_score": 9,
                "traffic_light": "blue",
                "summary": "Leadership asset with strong AI narrative and momentum.",
            },
            {
                "symbol": "MSFT",
                "setup_score": 7,
                "traffic_light": "green",
                "summary": "Durable enterprise quality with defensive upside.",
            },
        ]
    }


@app.post("/dashboard/upload")
async def dashboard_upload(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename)
    target = os.path.join(UPLOAD_DIR, filename)

    with open(target, "wb") as f:
        content = await file.read()
        f.write(content)

    assets = load_json(ASSETS_FILE, [])
    asset = {
        "filename": filename,
        "kind": "file",
        "mime_type": file.content_type,
    }
    assets.append(asset)
    save_json(ASSETS_FILE, assets)

    return {"ok": True, "asset": asset}


@app.get("/dashboard/assets")
def dashboard_assets():
    return {"assets": load_json(ASSETS_FILE, [])}
