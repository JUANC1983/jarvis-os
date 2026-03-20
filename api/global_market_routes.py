from fastapi import APIRouter

from core.global_market_intelligence_system import GlobalMarketIntelligenceSystem

router = APIRouter(prefix="/global-intel", tags=["global-intelligence"])
engine = GlobalMarketIntelligenceSystem()


@router.get("/scan")
def global_scan():
    return engine.scan()


@router.get("/markets")
def global_markets():
    return {
        "market_snapshot": engine.market_snapshot()
    }


@router.get("/news")
def global_news():
    return engine.news_brief()


@router.get("/risk")
def global_risk():
    return engine.risk_matrix()


@router.get("/commodity-regime")
def commodity_regime():
    return engine.commodity_regime()


@router.get("/liquidity-regime")
def liquidity_regime():
    return engine.volatility_and_liquidity_regime()


@router.get("/sector-rotation")
def sector_rotation():
    return engine.sector_rotation()


@router.get("/crypto-view")
def crypto_view():
    return engine.crypto_risk_view()
