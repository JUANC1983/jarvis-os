from fastapi import APIRouter
from core.product_brain import ProductBrain

router = APIRouter()
brain = ProductBrain()

AUTO_MODE = False

@router.post("/auto/toggle")
def toggle_auto():
    global AUTO_MODE
    AUTO_MODE = not AUTO_MODE
    return {"auto_mode": AUTO_MODE}

@router.get("/auto/status")
def status():
    return {"auto_mode": AUTO_MODE}
