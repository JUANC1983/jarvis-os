from fastapi import APIRouter

from core.trader_alpha_engine import TraderAlphaEngine

router = APIRouter(prefix="/trader-alpha", tags=["trader-alpha"])
engine = TraderAlphaEngine()

@router.post("/analyze")
def analyze(payload: dict):
    return engine.analyze(payload.get("symbol", ""))
