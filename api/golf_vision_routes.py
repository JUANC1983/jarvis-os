from fastapi import APIRouter
from core.golf_swing_vision_pro import GolfSwingVisionPro

router = APIRouter(prefix="/golf-vision")

vision = GolfSwingVisionPro()

@router.post("/analyze")

def analyze(payload:dict):

    video = payload.get("video")

    return vision.analyze(video)

