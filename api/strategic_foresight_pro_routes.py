from fastapi import APIRouter, HTTPException

from core.strategic_foresight_engine import StrategicForesightEngine

router = APIRouter(prefix="/foresight-pro", tags=["foresight-pro"])
engine = StrategicForesightEngine()


@router.post("/simulate")
def simulate(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")

    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")

    return engine.simulate(topic=topic, context=context)
