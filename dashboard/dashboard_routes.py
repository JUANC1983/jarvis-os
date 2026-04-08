from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime
import shutil
import os

from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.product_brain_pro import ProductBrainPro

router = APIRouter(prefix="/dashboard")

workspace = DashboardWorkspaceEngine()
brain = ProductBrainPro()

UPLOAD_DIR = "dashboard/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# =========================
# SERVE REAL DASHBOARD
# =========================

@router.get("/")
def serve_dashboard():
    return FileResponse("dashboard/jarvis_futuristic.html")


# =========================
# HOME (MAIN DATA)
# =========================

@router.get("/home")
def home():
    return workspace.home("Juan Camilo")


# =========================
# TASKS
# =========================

@router.post("/tasks")
def add_task(payload: dict):
    return workspace.add_task(
        text=payload.get("text"),
        priority=payload.get("priority", "medium"),
        day=payload.get("day", "today")
    )


@router.post("/tasks/{task_id}/toggle")
def toggle_task(task_id: str):
    return workspace.toggle_task(task_id)


# =========================
# MEETINGS
# =========================

@router.get("/meetings")
def get_meetings():
    data = workspace.home("Juan Camilo")
    return {
        "meetings": data.get("meetings", []),
        "next_meeting": data.get("next_meeting")
    }


@router.post("/meetings")
def add_meeting(payload: dict):
    created = workspace.add_meeting(
        title=payload.get("title"),
        time_value=payload.get("time"),
        notes=payload.get("notes", "")
    )
    return {
        "status": "ok",
        "meeting_created": created
    }


# =========================
# TRADER
# =========================

@router.post("/trader")
def trader(payload: dict):
    symbol = payload.get("symbol", "AAPL")
    result = brain.analyze_asset(symbol)

    trader_data = result.get("trader", {}) or {}
    trade_plan = trader_data.get("trade_plan", {}) or {}

    return {
        "symbol": result.get("symbol"),
        "price_now": result.get("price"),
        "setup_score": result.get("setup_score"),
        "traffic_light": trader_data.get("traffic_light"),
        "trade_plan": trade_plan,
        "summary": trader_data.get("summary"),
        "insight_lines": [
            x for x in [
                trader_data.get("summary"),
                result.get("macro_summary")
            ] if x
        ]
    }


# =========================
# RECOMMENDATIONS
# =========================

@router.get("/recommendations")
def recommendations():
    raw = brain.recommendations()
    items = raw.get("items", [])

    normalized = []
    for item in items:
        trader_data = item.get("trader", {}) or {}
        normalized.append({
            "symbol": item.get("symbol"),
            "price_now": item.get("price"),
            "setup_score": item.get("setup_score"),
            "traffic_light": trader_data.get("traffic_light"),
            "friendly_recommendation": trader_data.get("summary") or item.get("decision", {}).get("label", "")
        })

    return {
        "items": normalized,
        "engine": raw.get("engine", "PRO")
    }


# =========================
# SYSTEM METRICS
# =========================

@router.get("/system")
def system_metrics():
    recs = recommendations()
    items = recs.get("items", [])

    signals = len(items)
    scores = [x.get("setup_score", 0) or 0 for x in items]
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    if avg_score >= 75:
        risk = "controlled"
    elif avg_score >= 50:
        risk = "moderate"
    else:
        risk = "defensive"

    return {
        "signals": signals,
        "accuracy": f"{avg_score}%",
        "risk": risk,
        "exposure": f"${signals * 500}"
    }


# =========================
# AGENTS
# =========================

@router.get("/agents")
def agents():
    return {
        "items": [
            {"name": "Market Data Agent", "status": "scanning"},
            {"name": "News Intelligence Agent", "status": "monitoring"},
            {"name": "Macro Regime Agent", "status": "active"},
            {"name": "Opportunity Scoring Agent", "status": "ranking"},
            {"name": "Trader Decision Agent", "status": "ready"},
            {"name": "Calendar Intelligence Agent", "status": "standby"},
            {"name": "Golf Intelligence Agent", "status": "tracking"},
            {"name": "Memory Agent", "status": "recording"}
        ]
    }


# =========================
# NEWS
# =========================

@router.get("/news")
def news():
    return {
        "items": [
            {"title": "Markets monitor macro regime and large-cap momentum", "source": "JARVIS Markets"},
            {"title": "AI leaders remain in focus as compute demand stays elevated", "source": "JARVIS Tech"},
            {"title": "Golf module ready for training, scheduling and performance tracking", "source": "JARVIS Golf"},
            {"title": "Execution dashboard upgraded with pipeline, agents and system metrics", "source": "JARVIS OS"}
        ]
    }


# =========================
# ASSETS
# =========================

@router.get("/assets")
def assets():
    return workspace.list_assets()


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    workspace.register_asset(
        filename=file.filename,
        stored_path=file_path,
        mime_type=file.content_type
    )

    return {"status": "uploaded", "filename": file.filename}


@router.get("/uploads/{filename}")
def uploaded_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(file_path)
