from datetime import datetime
from pathlib import Path
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain
from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.meetings_engine import MeetingsEngine
from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.news_intelligence_engine import NewsIntelligenceEngine
from core.golf_dashboard_engine import GolfDashboardEngine

app = FastAPI(title="JARVIS OS")
brain = ProductBrain()
workspace = DashboardWorkspaceEngine()
meetings_engine = MeetingsEngine()
orchestrator = AgentOrchestratorPro()
news_engine   = NewsIntelligenceEngine()
golf_engine   = GolfDashboardEngine()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_HTML = BASE_DIR / "dashboard" / "jarvis_futuristic.html"
UPLOADS_DIR = BASE_DIR / "dashboard" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


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


# =========================
# HOME — persistent tasks + meetings
# =========================
@app.get("/dashboard/home")
def dashboard_home():
    try:
        return workspace.home("Juan Camilo")
    except Exception as e:
        return {
            "greeting": "JARVIS ready",
            "date": datetime.now().strftime("%A %d %B %Y"),
            "owner_name": "Juan Camilo",
            "top_priority": "Protect capital",
            "tasks_open": 0,
            "assets_count": 0,
            "next_meeting": None,
            "tasks": [],
            "meetings": [],
        }


# =========================
# CHAT
# =========================
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


# =========================
# AUTO JARVIS
# =========================
@app.post("/jarvis/auto")
def jarvis_auto():
    try:
        recs = brain.recommendations()
        items = recs.get("items", [])[:5]

        if not items:
            return {"reply": "No encuentro setups claros en este momento.", "items": []}

        top = ", ".join([f"{x['symbol']} (score {x['setup_score']})" for x in items[:3]])
        return {
            "reply": f"Auto JARVIS completado. Mejores setups ahora: {top}.",
            "items": items,
        }
    except Exception as e:
        return {"reply": f"Auto JARVIS error: {e}", "items": []}


# =========================
# TRADER
# =========================
@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        symbol = data.get("symbol", "AAPL")
        return brain.trader(symbol)
    except Exception as e:
        return {"error": str(e)}


# =========================
# RECOMMENDATIONS
# =========================
@app.get("/dashboard/recommendations")
def recommendations():
    try:
        return brain.recommendations()
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# TASKS — persistent
# =========================
@app.post("/dashboard/tasks")
def add_task(data: dict):
    try:
        text = (data.get("text") or "").strip()
        priority = (data.get("priority") or "medium").strip().lower()
        day = (data.get("day") or "today").strip().lower()

        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        if priority not in ["high", "medium", "low"]:
            priority = "medium"

        return workspace.add_task(text, priority, day)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: str):
    try:
        return workspace.toggle_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# =========================
# MEETINGS — persistent
# =========================
@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    try:
        title = (data.get("title") or "").strip()
        time_value = (data.get("time") or "").strip()
        notes = (data.get("notes") or "").strip()

        if not title or not time_value:
            raise HTTPException(status_code=400, detail="title and time are required")

        return workspace.add_meeting(title, time_value, notes)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =========================
# SCHEDULE MEETING (from floating button)
# =========================
@app.post("/dashboard/schedule-meeting")
def schedule_meeting(data: dict):
    try:
        objective = (data.get("objective") or "").strip()
        datetime_value = (data.get("datetime") or "").strip()

        if not objective or not datetime_value:
            raise HTTPException(status_code=400, detail="objective and datetime are required")

        meeting = meetings_engine.add_meeting_datetime(
            title=objective,
            datetime_value=datetime_value,
            notes="Scheduled via dashboard"
        )
        return {"status": "ok", "meeting_created": meeting}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =========================
# ASSETS — persistent
# =========================
@app.get("/dashboard/assets")
def assets():
    try:
        return workspace.list_assets()
    except Exception:
        return {"assets": []}


@app.post("/dashboard/upload")
async def upload_asset(file: UploadFile = File(...)):
    try:
        filename = (file.filename or "asset.bin").replace("/", "_").replace("\\", "_")
        output_path = UPLOADS_DIR / filename

        with output_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        item = workspace.register_asset(
            filename=filename,
            stored_path=str(output_path),
            mime_type=file.content_type,
            size_bytes=output_path.stat().st_size,
        )
        return {"status": "ok", "asset": item}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/dashboard/uploads/{filename:path}")
def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


# =========================
# SYSTEM METRICS
# =========================
@app.get("/dashboard/system")
def system_metrics():
    return {
        "signals": 3,
        "accuracy": "72%",
        "risk": "medium",
        "exposure": "45%"
    }


# =========================
# AGENTS — real orchestrator state
# =========================
@app.get("/dashboard/agents")
def agents():
    try:
        items = orchestrator.agent_status_snapshot()
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# NEWS FEED — real categorised RSS via NewsIntelligenceEngine
# =========================
@app.get("/dashboard/news")
def news():
    try:
        items = news_engine.fetch_categorized(max_per_category=5)
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# GOLF — wires GolfCourseDatabase + Open-Meteo weather
# =========================
@app.get("/dashboard/golf")
def golf():
    try:
        return golf_engine.dashboard_summary(max_courses=6)
    except Exception as e:
        return {
            "courses":      [],
            "insights":     ["Golf data temporarily unavailable."],
            "player":       {},
            "generated_at": datetime.now().isoformat(),
            "error":        str(e),
        }
