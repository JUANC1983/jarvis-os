class NarrativeDetectionEngine:
    def analyze(self, topic: str, context: str = "") -> dict:
        text = f"{topic} {context}".lower()

        dominant_narratives = []
        risks = []
        opportunities = []

        if any(w in text for w in ["war", "guerra", "iran", "israel", "middle east"]):
            dominant_narratives.append("Geopolitical energy shock narrative")
            risks.extend([
                "Volatility spikes",
                "Policy uncertainty",
                "Energy inflation pass-through",
            ])
            opportunities.extend([
                "Oil strength",
                "Defense exposure",
                "Volatility instruments",
            ])

        if any(w in text for w in ["ai", "artificial intelligence", "semiconductor", "chips"]):
            dominant_narratives.append("AI productivity / compute demand narrative")
            risks.extend([
                "Crowded positioning",
                "Valuation compression",
            ])
            opportunities.extend([
                "Semiconductor beneficiaries",
                "Infrastructure and compute chain",
            ])

        if any(w in text for w in ["inflation", "inflacion", "rates", "fed", "tasas", "usd", "dollar"]):
            dominant_narratives.append("Inflation / rates regime narrative")
            risks.extend([
                "Rate repricing",
                "Cross-asset drawdown risk",
            ])
            opportunities.extend([
                "Gold",
                "Commodities",
                "Selective macro hedges",
            ])

        if not dominant_narratives:
            dominant_narratives.append("No dominant market narrative clearly detected")

        summary = (
            f"Narrative engine analyzed topic '{topic}' and found "
            f"{len(dominant_narratives)} dominant narrative(s)."
        )

        return {
            "topic": topic,
            "dominant_narratives": dominant_narratives,
            "risks": risks,
            "opportunities": opportunities,
            "summary": summary,
        }
