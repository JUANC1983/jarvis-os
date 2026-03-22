from fastapi import FastAPI
from pydantic import BaseModel
from core.product_brain import ProductBrain

app = FastAPI()
brain = ProductBrain()

class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


# ✅ FIX: endpoint que el dashboard espera
@app.get("/dashboard")
def dashboard_root():
    return {"status": "dashboard connected"}


# ✅ CHAT BLINDADO
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = brain.chat(req.message)

        return {
            "status": "ok",
            "response": result
        }

    except Exception as e:
        return {
            "status": "error",
            "response": str(e)
        }


# ✅ TRADER
@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        return brain.trader(data.get("symbol", "AAPL"))
    except Exception as e:
        return {"error": str(e)}


# ✅ RECOMMENDATIONS
@app.get("/dashboard/recommendations")
def recommendations():
    try:
        return brain.recommendations()
    except Exception as e:
        return {"error": str(e)}
