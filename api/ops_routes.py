from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.ops_observability_engine import OpsObservabilityEngine
from core.executive_briefing_engine import ExecutiveBriefingEngine

router = APIRouter(prefix="/ops", tags=["ops"])
obs = OpsObservabilityEngine()
briefing = ExecutiveBriefingEngine()

@router.get("/events")
def events(limit: int = 50):
    return obs.tail(limit)

@router.post("/log")
def log(payload: dict):
    return obs.log(payload.get("event_type", "generic"), payload.get("payload", {}))

@router.get("/briefing")
def get_briefing(topic: str = "global macro", context: str = ""):
    return briefing.build(topic=topic, context=context)

@router.get("/dashboard")
def dashboard():
    path = Path("dashboard/jarvis_futuristic.html")
    if not path.exists():
        raise HTTPException(status_code=404, detail="dashboard not found")
    return FileResponse(path)
