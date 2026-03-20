class AlertEngine:
    def __init__(self):
        self.alerts = []

    def create(self, symbol: str, condition: str, threshold: float, note: str = ""):
        alert = {
            "symbol": symbol.upper(),
            "condition": condition,
            "threshold": threshold,
            "note": note,
        }
        self.alerts.append(alert)
        return alert

    def list_alerts(self):
        return self.alerts

    def evaluate(self):
        return {
            "triggered": [],
            "checked": len(self.alerts),
        }
