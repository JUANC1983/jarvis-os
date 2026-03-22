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


@app.get("/dashboard")
def dashboard_root():
    return {"status": "dashboard connected"}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = brain.respond(req.message)

        return {
            "status": "ok",
            "response": result
        }

    except Exception as e:
        return {
            "status": "error",
            "response": str(e)
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


@app.get("/dashboard/assets")
def assets():
    return {"assets": []}


@app.post("/dashboard/tasks")
def add_task(data: dict):
    return {"status": "ok"}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    return {"status": "ok"}


@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    return {"status": "ok"}
