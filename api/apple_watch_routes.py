from fastapi import APIRouter
from core.golf_ai_agent import GolfAIAgent

router = APIRouter(prefix="/watch", tags=["apple_watch"])
golf = GolfAIAgent()

@router.post("/caddie")
def apple_watch_caddie(payload: dict):
    return golf.watch_ready_payload(
        latitude=float(payload.get("latitude")),
        longitude=float(payload.get("longitude")),
        distance_front=float(payload.get("distance_front")),
        distance_middle=float(payload.get("distance_middle")),
        distance_back=float(payload.get("distance_back")),
        hole_number=payload.get("hole_number"),
        player_profile=payload.get("player_profile", {})
    )