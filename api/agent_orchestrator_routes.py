from fastapi import APIRouter

from core.agent_orchestrator_pro import AgentOrchestratorPro

router = APIRouter(prefix="/agent-orchestrator", tags=["agent-orchestrator"])
engine = AgentOrchestratorPro()


@router.post("/route")
def route(payload: dict):
    return engine.route(payload.get("domain", "general"))


@router.post("/deliberate")
def deliberate(payload: dict):
    return engine.deliberate(
        query=payload.get("query", ""),
        domain=payload.get("domain", "general"),
    )
