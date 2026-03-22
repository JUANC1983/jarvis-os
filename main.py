from fastapi import FastAPI
from pydantic import BaseModel
from core.product_brain import ProductBrain

app = FastAPI()

brain = ProductBrain()


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "JARVIS OS RUNNING"}


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
            "message": str(e)
        }


@app.post("/dashboard/trader")
def trader(data: dict):
    symbol = data.get("symbol", "AAPL")
    return brain.trader(symbol)


@app.get("/dashboard/recommendations")
def recommendations():
    return brain.recommendations()
