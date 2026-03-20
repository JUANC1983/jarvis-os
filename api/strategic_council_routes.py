from fastapi import APIRouter

from core.decision.strategic_council_engine import StrategicCouncilEngine

router = APIRouter(prefix="/strategic-council", tags=["strategic-council"])
engine = StrategicCouncilEngine()


@router.post("/deliberate")
def deliberate(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return engine.deliberate(topic=topic, context=context)
