from fastapi import APIRouter
from datetime import datetime

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

        "meetings":[
            {"time":"15:00","title":"Strategy Review"}
        ],

        "recommended_stocks":[
            {"symbol":"NVDA","score":88},
            {"symbol":"MSFT","score":82}
        ]
    }