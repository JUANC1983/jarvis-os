class CalendarIntelligenceEngine:
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
