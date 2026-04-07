from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse
from datetime import datetime
import shutil
import os

from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.product_brain_pro import ProductBrainPro

router = APIRouter(prefix="/dashboard")

workspace = DashboardWorkspaceEngine()
brain = ProductBrainPro()

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

@router.post("/meetings")
def add_meeting(payload: dict):
    return workspace.add_meeting(
        title=payload.get("title"),
        time_value=payload.get("time"),
        notes=payload.get("notes", "")
    )


# =========================
# TRADER
# =========================

@router.post("/trader")
def trader(payload: dict):
    symbol = payload.get("symbol", "AAPL")
    result = brain.analyze_asset(symbol)

    return {
        "symbol": result.get("symbol"),
        "price_now": result.get("price"),
        "setup_score": result.get("setup_score"),
        "traffic_light": result.get("trader", {}).get("traffic_light"),
        "trade_plan": result.get("trader", {}).get("trade_plan"),
        "summary": result.get("trader", {}).get("summary"),
        "insight_lines": [result.get("macro_summary", "")]
    }


# =========================
# RECOMMENDATIONS
# =========================

@router.get("/recommendations")
def recommendations():
    return brain.recommendations()


# =========================
# ASSETS
# =========================

UPLOAD_DIR = "dashboard/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
