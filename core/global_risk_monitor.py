class GlobalRiskMonitor:
    def assess(self, topic: str, context: str = "") -> dict:
        text = f"{topic} {context}".lower()

        risk_level = "moderate"
        risk_score = 55
        risk_factors = []
        protections = []

        if any(w in text for w in ["war", "guerra", "iran", "israel", "middle east", "taiwan", "china"]):
            risk_level = "high"
            risk_score = 78
            risk_factors.extend([
                "Geopolitical escalation",
                "Energy and shipping disruption risk",
                "Cross-asset volatility",
            ])
            protections.extend([
                "Reduce leverage",
                "Increase hedging awareness",
                "Stress test downside scenarios",
            ])

        if any(w in text for w in ["inflation", "inflacion", "rates", "fed", "tasas", "usd", "dollar"]):
            risk_score += 8
            risk_factors.append("Rates / inflation repricing risk")
            protections.append("Avoid concentration in one macro view")

        if any(w in text for w in ["medical", "pain", "symptom", "dolor", "hombro", "urgent", "emergency", "emergencia"]):
            risk_level = "high"
            risk_score = max(risk_score, 82)
            risk_factors.append("Potential health escalation")
            protections.append("Escalate to qualified in-person care if red flags appear")

        if not risk_factors:
            risk_factors.append("No critical risk cluster detected")
            protections.append("Maintain baseline risk discipline")

        return {
            "risk_level": risk_level,
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
            "protections": protections,
            "summary": f"Global risk monitor assessed '{topic}' with score {min(risk_score, 100)}."
        }
