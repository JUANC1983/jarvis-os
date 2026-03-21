import json
from datetime import datetime
from pathlib import Path

AUDIT_PATH = Path("data/secure_execution_audit.jsonl")

def log_event(event_type: str, payload: dict):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
