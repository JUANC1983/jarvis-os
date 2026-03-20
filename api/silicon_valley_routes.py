from fastapi import APIRouter

from core.vector_memory_pro import VectorMemoryPro
from core.system_guardrails_engine import SystemGuardrailsEngine

router = APIRouter(prefix="/silicon-valley", tags=["silicon-valley"])
memory_engine = VectorMemoryPro()
guardrails = SystemGuardrailsEngine()


@router.post("/memory/store")
def store(payload: dict):
    return memory_engine.store(
        text=payload.get("text", ""),
        category=payload.get("category", "general"),
        metadata=payload.get("metadata", {}),
    )


@router.post("/memory/search")
def search(payload: dict):
    return memory_engine.search(
        query=payload.get("query", ""),
        k=int(payload.get("k", 5)),
    )


@router.get("/memory/categories")
def categories():
    return memory_engine.categories()


@router.post("/guardrails/check")
def guardrail_check(payload: dict):
    return guardrails.evaluate(payload.get("text", ""))
