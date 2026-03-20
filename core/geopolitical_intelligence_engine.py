from core.live_news_engine import LiveNewsEngine


class GeopoliticalIntelligenceEngine:
    def __init__(self):
        self.news = LiveNewsEngine()

    def analyze(self, topic: str, context: str = "") -> dict:
        text = f"{topic} {context}".lower()

        signals = []
        risks = []
        opportunities = []
        narratives = []

        if any(w in text for w in ["war", "guerra", "iran", "israel", "middle east", "taiwan", "china"]):
            signals.append("Geopolitical escalation signal")
            risks.extend([
                "Energy supply shock",
                "Inflation spillover",
                "Cross-asset volatility increase",
            ])
            opportunities.extend([
                "Oil upside exposure",
                "Defense sector beneficiaries",
                "Volatility and hedging opportunities",
            ])
            narratives.append("Energy shock / geopolitical risk narrative")

        if any(w in text for w in ["inflation", "inflacion", "rates", "tasas", "usd", "dollar", "gold"]):
            signals.append("Inflation / hard asset regime signal")
            risks.extend([
                "Rates repricing",
                "Duration pressure",
            ])
            opportunities.extend([
                "Gold",
                "Selective commodity exposure",
                "Macro hedges",
            ])
            narratives.append("Hard assets vs rates narrative")

        news = self.news.fetch()

        return {
            "topic": topic,
            "context": context,
            "signals": signals or ["No strong geopolitical signal detected."],
            "risks": risks,
            "opportunities": opportunities,
            "narratives": narratives,
            "live_news_sample": news[:5],
            "summary": f"Geopolitical intelligence analyzed '{topic}'.",
        }
