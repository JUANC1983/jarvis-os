from datetime import datetime
from core.audit_engine import AuditEngine


class LearningEngine:
    def __init__(self):
        self.audit = AuditEngine()

    def learn_from_decision(self, decision: str, outcome: str, score: float = 0.0, notes: str = ""):
        record = {
            "decision": decision,
            "outcome": outcome,
            "score": score,
            "notes": notes,
            "learned_at": datetime.utcnow().isoformat(),
            "learning": "Pattern stored for future strategic recall.",
        }
        self.audit.log_event("learning_feedback", record)
        return record
