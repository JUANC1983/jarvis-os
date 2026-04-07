from core.meetings_engine import MeetingsEngine

def cleanup_meetings_job():
    engine = MeetingsEngine()
    removed = engine.cleanup_past_meetings()
    print(f"[Scheduler] cleaned meetings: {removed}")
