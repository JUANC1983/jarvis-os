from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


class OpsObservabilityEngine:
    def __init__(self, log_path: str = "logs/ops_events.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")

    def log(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return {"status": "ok", "logged": event_type}

    def tail(self, limit: int = 50) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        return {"count": len(rows[-limit:]), "events": rows[-limit:]}
