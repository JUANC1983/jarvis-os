import json
import os
from datetime import datetime


class AlertStore:
    def __init__(self, filepath: str = "data/alerts.json"):
        self.filepath = filepath
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load(self):
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, alerts):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)

    def add_alert(self, symbol: str, condition: str, threshold: float, note: str = ""):
        alerts = self.load()
        alert = {
            "id": len(alerts) + 1,
            "symbol": symbol.upper(),
            "condition": condition,
            "threshold": threshold,
            "note": note,
            "created_at": datetime.utcnow().isoformat(),
        }
        alerts.append(alert)
        self.save(alerts)
        return alert
