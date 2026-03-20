import json
import os
from datetime import datetime


class AuditEngine:
    def __init__(self, filepath: str = "data/audit_events.jsonl"):
        self.filepath = filepath
        os.makedirs("data", exist_ok=True)

    def log_event(self, event_type: str, payload: dict):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def read_events(self, limit: int = 50):
        if not os.path.exists(self.filepath):
            return []

        events = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue

        return events[-limit:]
