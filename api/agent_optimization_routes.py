from fastapi import APIRouter

from core.agent_optimization_engine import AgentOptimizationEngine

router = APIRouter(prefix="/agent-optimization", tags=["agent-optimization"])
engine = AgentOptimizationEngine()

@router.get("/registry")
def registry():
    return engine.registry.list_agents()

@router.post("/optimize")
def optimize(payload: dict):
    return engine.optimize_for_domain(payload.get("domain", "general"))

@router.post("/layout")
def layout(payload: dict):
    return engine.premium_council_layout(payload.get("domain", "general"))
