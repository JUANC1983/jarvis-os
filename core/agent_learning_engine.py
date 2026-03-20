from datetime import datetime
from core.audit_engine import AuditEngine


class AgentLearningEngine:
    def __init__(self):
        self.audit = AuditEngine()

    def store_feedback(self, decision: str, outcome: str, score: float = 0.0, notes: str = ""):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "decision": decision,
            "outcome": outcome,
            "score": score,
            "notes": notes,
        }
        self.audit.log_event("learning_feedback", record)
        return record

    def summary(self):
        events = self.audit.read_events(200)
        learning_events = [e for e in events if e.get("event_type") == "learning_feedback"]
        scores = [e["payload"].get("score", 0) for e in learning_events if isinstance(e["payload"].get("score", 0), (int, float))]
        average_score = round(sum(scores) / len(scores), 4) if scores else None

        return {
            "count": len(learning_events),
            "average_score": average_score,
            "recent": learning_events[-10:],
        }
