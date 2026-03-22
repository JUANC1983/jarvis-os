from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain

app = FastAPI()
brain = ProductBrain()

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DASHBOARD_HTML = DASHBOARD_DIR / "jarvis_futuristic.html"
FALLBACK_HTML = DASHBOARD_DIR / "app.html"


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/dashboard")
def dashboard_root():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    if FALLBACK_HTML.exists():
        return FileResponse(FALLBACK_HTML)
    raise HTTPException(status_code=404, detail="Dashboard HTML not found")


@app.get("/favicon.ico")
def favicon():
    raise HTTPException(status_code=404, detail="Not Found")


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = brain.chat(req.message)
        return {
            "status": "ok",
            "response": result,
        }
    except Exception as e:
        return {
            "status": "error",
            "response": str(e),
        }


@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        return brain.trader(data.get("symbol", "AAPL"))
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard/recommendations")
def recommendations():
    try:
        return brain.recommendations()
    except Exception as e:
        return {"error": str(e)}
