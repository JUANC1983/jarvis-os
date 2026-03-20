from fastapi import APIRouter

from core.premium_opportunity_engine import PremiumOpportunityEngine

router = APIRouter(prefix="/opportunity", tags=["opportunity"])
engine = PremiumOpportunityEngine()


@router.get("/watchlist/default")
def default_watchlist():
    return {
        "watchlist": engine.get_default_watchlist()
    }


@router.post("/ticker")
def analyze_ticker(payload: dict):
    symbol = payload.get("symbol", "")
    topic = payload.get("topic", "")
    context = payload.get("context", "")

    return engine.analyze_symbol(
        symbol=symbol,
        topic=topic,
        context=context,
    )


@router.post("/premium-scan")
def premium_scan(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    symbols = payload.get("symbols", None)

    return engine.premium_scan(
        topic=topic,
        context=context,
        symbols=symbols,
    )


@router.post("/watchlist/custom")
def custom_watchlist(payload: dict):
    symbols = payload.get("symbols", [])
    topic = payload.get("topic", "")
    context = payload.get("context", "")

    return engine.scan_symbols(
        symbols=symbols,
        topic=topic,
        context=context,
    )
