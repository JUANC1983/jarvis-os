from fastapi import APIRouter, HTTPException

from core.global_opportunity_radar_pro import GlobalOpportunityRadarPro

router = APIRouter(prefix="/opportunity-pro", tags=["opportunity-pro"])
engine = GlobalOpportunityRadarPro()


@router.get("/watchlist/default")
def watchlist_default():
    return {"watchlist": engine.get_default_watchlist()}


@router.post("/ticker")
def analyze_ticker(payload: dict):
    symbol = payload.get("symbol", "").strip()
    topic = payload.get("topic", "")
    context = payload.get("context", "")

    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    return engine.analyze_symbol(symbol=symbol, topic=topic, context=context)


@router.post("/scan")
def scan(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    symbols = payload.get("symbols", None)

    return engine.scan(topic=topic, context=context, symbols=symbols)


@router.post("/high-priority")
def high_priority(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    symbols = payload.get("symbols", None)

    result = engine.scan(topic=topic, context=context, symbols=symbols)
    return {
        "high_priority_setups": result["high_priority_setups"],
        "risk_matrix": result["risk_matrix"],
        "executive_summary": result["executive_summary"],
    }
