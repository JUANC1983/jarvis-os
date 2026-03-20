class GlobalIntelligenceEngine:
    def analyze(self, topic: str, context: str = "") -> dict:
        text = f"{topic} {context}".lower()

        signals = []
        risks = []
        opportunities = []
        narratives = []

        if any(w in text for w in ["war", "guerra", "iran", "israel", "china", "taiwan", "middle east"]):
            signals.append("Geopolitical escalation signal")
            narratives.append("Energy shock narrative")
            risks.extend([
                "Energy supply disruption",
                "Global inflation shock",
                "Shipping routes instability",
            ])
            opportunities.extend([
                "Oil upside trades",
                "Defense sector equities",
                "Volatility trades",
            ])

        if any(w in text for w in ["inflation", "inflacion", "rates", "tasas", "fed", "usd", "dollar"]):
            signals.append("Inflation / rates regime signal")
            narratives.append("Hard-assets vs rate pressure narrative")
            risks.extend([
                "Rate shock repricing",
                "Bond volatility",
            ])
            opportunities.extend([
                "Gold",
                "Commodities",
                "Selective macro hedges",
            ])

        if not signals:
            signals.append("No major macro signals detected")

        return {
            "signals": signals,
            "risks": risks,
            "opportunities": opportunities,
            "narratives": narratives,
            "summary": f"Global intelligence analyzed topic '{topic}'.",
        }
