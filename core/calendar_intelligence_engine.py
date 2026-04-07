from datetime import datetime, timedelta
from core.meetings_engine import MeetingsEngine


class CalendarIntelligenceEngine:

    def __init__(self):
        self.meetings = MeetingsEngine()

    def plan(self, objective: str, duration_minutes: int = 60, participants=None):
        participants = participants or []

        return {
            "objective": objective,
            "duration_minutes": duration_minutes,
            "participants": participants,
            "agenda": [
                "Context and objective",
                "Decision points",
                "Risks and constraints",
                "Next steps and owners",
            ],
            "status": "calendar planning scaffold ready",
        }

    def schedule_meeting(
        self,
        objective: str,
        datetime_str: str,
        duration_minutes: int = 60,
        participants=None,
    ):
        """
        FULL FLOW:
        1. Plan meeting
        2. Create real meeting in MeetingsEngine
        """

        plan = self.plan(objective, duration_minutes, participants)

        meeting = self.meetings.add_meeting_datetime(
            title=objective,
            datetime_str=datetime_str,
            notes=" | ".join(plan["agenda"])
        )

        return {
            "plan": plan,
            "meeting_created": meeting,
            "status": "scheduled"
        }