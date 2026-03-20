from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.document_intelligence_engine import DocumentIntelligenceEngine
from core.market_intelligence_engine import MarketIntelligenceEngine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

workspace = DashboardWorkspaceEngine()
document_engine = DocumentIntelligenceEngine()
market_engine = MarketIntelligenceEngine()

DASHBOARD_DIR = Path("dashboard")
UPLOADS_DIR = DASHBOARD_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _owner_name() -> str:
    return "Juan Camilo Montenegro"


def _dashboard_file() -> Path:
    premium = DASHBOARD_DIR / "jarvis_futuristic.html"
    app_html = DASHBOARD_DIR / "app.html"
    index_html = DASHBOARD_DIR / "index.html"

    if premium.exists():
        return premium
    if app_html.exists():
        return app_html
    if index_html.exists():
        return index_html

    raise HTTPException(status_code=404, detail="dashboard html not found")


@router.get("/app")
def dashboard_app():
    return FileResponse(_dashboard_file())


@router.get("/app.html")
def dashboard_app_html():
    return FileResponse(_dashboard_file())


@router.get("/manifest.json")
def dashboard_manifest():
    path = DASHBOARD_DIR / "manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="manifest not found")
    return FileResponse(path, media_type="application/manifest+json")


@router.get("/sw.js")
def dashboard_sw():
    path = DASHBOARD_DIR / "sw.js"
    if not path.exists():
        raise HTTPException(status_code=404, detail="service worker not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="application/javascript")


@router.get("/home")
def dashboard_home():
    return workspace.home(_owner_name())


@router.get("/assets")
def dashboard_assets():
    return workspace.list_assets()


@router.post("/tasks")
def add_task(payload: dict):
    text = (payload.get("text") or "").strip()
    priority = (payload.get("priority") or "medium").strip().lower()
    day = (payload.get("day") or "today").strip().lower()

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    if priority not in ["high", "medium", "low"]:
        priority = "medium"

    return workspace.add_task(text, priority, day)


@router.post("/tasks/{task_id}/toggle")
def toggle_task(task_id: str):
    try:
        return workspace.toggle_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/meetings")
def add_meeting(payload: dict):
    title = (payload.get("title") or "").strip()
    time_value = (payload.get("time") or "").strip()
    notes = (payload.get("notes") or "").strip()

    if not title or not time_value:
        raise HTTPException(status_code=400, detail="title and time are required")

    return workspace.add_meeting(title, time_value, notes)


@router.post("/upload")
async def upload_asset(file: UploadFile = File(...)):
    filename = (file.filename or "asset.bin").replace("/", "_").replace("\\", "_")
    output_path = UPLOADS_DIR / filename

    with output_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    item = workspace.register_asset(
        filename=filename,
        stored_path=str(output_path),
        mime_type=file.content_type,
        size_bytes=output_path.stat().st_size,
    )

    return {"status": "ok", "asset": item}


@router.get("/uploads/{filename:path}")
def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


@router.post("/analyze-asset")
def analyze_asset(payload: dict):
    filename = (payload.get("filename") or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")

    return document_engine.analyze(str(path))


@router.get("/market/snapshot")
def market_snapshot():
    return market_engine.snapshot()


@router.post("/trader")
def dashboard_trader(payload: dict):
    raw = (payload.get("symbol") or "AAPL").strip()
    symbol = raw.upper()

    live = market_engine.analyze_symbol(symbol)

    if live.get("error"):
        return {
            "symbol": symbol,
            "setup_score": 50,
            "traffic_light": "orange",
            "technicals": {
                "price": None,
                "day_high": None,
                "day_low": None
            },
            "trade_plan": {
                "action": "Wait",
                "entry_zone": [],
                "stop_loss": None,
                "target_1": None,
                "target_2": None,
                "risk_reward_estimate": "-"
            },
            "narrative": [
                f"No se pudo obtener data suficiente para {symbol}."
            ],
            "summary": "Insufficient market data."
        }

    price = live["price"]
    day_high = live["day_high"]
    day_low = live["day_low"]
    ma20 = live["ma20"]
    ma50 = live["ma50"]
    trend = live["trend"]
    momentum = live["momentum"]

    traffic_light = "green" if trend == "bullish" else "orange"
    setup_score = 80 if trend == "bullish" and momentum == "strong" else 64

    return {
        "symbol": symbol,
        "setup_score": setup_score,
        "traffic_light": traffic_light,
        "technicals": {
            "price": price,
            "day_high": day_high,
            "day_low": day_low,
            "ma20": ma20,
            "ma50": ma50
        },
        "trade_plan": {
            "action": "Buy pullback" if trend == "bullish" else "Wait for confirmation",
            "entry_zone": [round(price * 0.985, 2), round(price * 0.995, 2)],
            "stop_loss": round(price * 0.96, 2),
            "target_1": round(price * 1.05, 2),
            "target_2": round(price * 1.10, 2),
            "risk_reward_estimate": "1:2.5" if trend == "bullish" else "1:1.2"
        },
        "narrative": [
            f"Tendencia principal: {trend}.",
            f"Momentum actual: {momentum}.",
            f"MA20: {ma20} / MA50: {ma50}.",
            "Conviene entrar con disciplina y no perseguir precio."
        ],
        "summary": f"{symbol} con sesgo {trend} y momentum {momentum}."
    }


@router.get("/recommendations")
def recommendations():
    snapshot = market_engine.snapshot()
    items = snapshot.get("items", [])

    ranked = []
    for item in items:
        score = 75
        if item["label"] == "NASDAQ":
            score = 84
        elif item["label"] == "QQQ":
            score = 82
        elif item["label"] == "SPY":
            score = 79

        ranked.append({
            "symbol": item["label"],
            "setup_score": score,
            "traffic_light": "green" if item["change_pct"] >= 0 else "orange",
            "reason": f"Precio {item['price']} | cambio {item['change_pct']}% | contexto de mercado en tiempo real."
        })

    return {"items": ranked}