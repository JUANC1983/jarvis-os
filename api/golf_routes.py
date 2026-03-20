from fastapi import APIRouter, HTTPException
from core.golf_ai_agent import GolfAIAgent

router = APIRouter(prefix="/golf", tags=["golf"])
agent = GolfAIAgent()

@router.post("/club")
def club(payload: dict):
    return agent.recommend_club(
        distance=float(payload.get("distance", 150)),
        wind_mph=float(payload.get("wind_mph", 0)),
        wind_direction=payload.get("wind_direction", "neutral"),
        elevation_delta_yards=float(payload.get("elevation_delta_yards", 0)),
        lie=payload.get("lie", "fairway"),
        temperature_c=float(payload.get("temperature_c", 22)),
        player_profile=payload.get("player_profile"),
    )

@router.post("/swing/analyze")
def swing_analyze(payload: dict):
    video_path = payload.get("video_path")
    if not video_path:
        raise HTTPException(status_code=400, detail="video_path is required")
    return agent.analyze_swing_video(video_path, payload.get("player_profile"))

@router.post("/swing/compare")
def swing_compare(payload: dict):
    video_path_a = payload.get("video_path_a")
    video_path_b = payload.get("video_path_b")
    if not video_path_a or not video_path_b:
        raise HTTPException(status_code=400, detail="video_path_a and video_path_b are required")
    return agent.compare_swings(
        video_path_a,
        video_path_b,
        payload.get("label_a", "before"),
        payload.get("label_b", "after"),
    )

@router.post("/fitting")
def fitting(payload: dict):
    return agent.fitting_recommendation(payload.get("player_profile"))

@router.post("/biometrics")
def biometrics(payload: dict):
    return agent.biometrics_profile(payload.get("player_profile"))

@router.post("/faults")
def faults(payload: dict):
    video_path = payload.get("video_path")
    if not video_path:
        raise HTTPException(status_code=400, detail="video_path is required")
    return agent.detect_swing_faults(video_path)

@router.post("/course/caddie")
def course_caddie(payload: dict):
    return agent.course_caddie(
        latitude=float(payload.get("latitude")),
        longitude=float(payload.get("longitude")),
        hole_number=payload.get("hole_number"),
    )

@router.post("/watch/payload")
def watch_payload(payload: dict):
    return agent.watch_ready_payload(
        latitude=float(payload.get("latitude")),
        longitude=float(payload.get("longitude")),
        distance_front=float(payload.get("distance_front")),
        distance_middle=float(payload.get("distance_middle")),
        distance_back=float(payload.get("distance_back")),
        hole_number=payload.get("hole_number"),
        player_profile=payload.get("player_profile"),
    )

@router.post("/courses/import")
def import_courses(payload: dict):
    json_path = payload.get("json_path")
    if not json_path:
        raise HTTPException(status_code=400, detail="json_path is required")
    return agent.import_courses_json(json_path)

@router.get("/courses/stats")
def course_stats():
    return agent.database_stats()

@router.post("/courses/search")
def course_search(payload: dict):
    query = payload.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    return agent.search_courses(query, limit=int(payload.get("limit", 10)))