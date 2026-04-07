from fastapi import APIRouter
from datetime import datetime
from core.meetings_engine import MeetingsEngine
from core.calendar_intelligence_engine import CalendarIntelligenceEngine

meetings_engine = MeetingsEngine()

router = APIRouter(prefix="/dashboard")

@router.get("/summary")
def dashboard_summary():

    return {

        "system_status":"online",

        "today":datetime.utcnow(),

        "priorities":[
            "Protect capital",
            "Review macro regime",
            "Evaluate top setups"
        ],

        "tasks":[
            {"task":"Review markets","priority":"high"},
            {"task":"Prepare strategy meeting","priority":"medium"}
        ],

        "meetings": meetings_engine.get_upcoming(),

        "recommended_stocks":[
            {"symbol":"NVDA","score":88},
            {"symbol":"MSFT","score":82}
        ]
    }
@router.post("/schedule-meeting")
def schedule_meeting(payload: dict):

    engine = CalendarIntelligenceEngine()

    return engine.schedule_meeting(
        objective=payload.get("objective"),
        datetime_str=payload.get("datetime"),
        duration_minutes=payload.get("duration", 60),
        participants=payload.get("participants", [])
    )
