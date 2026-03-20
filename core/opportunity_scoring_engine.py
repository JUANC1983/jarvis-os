class OpportunityScoringEngine:

    def score(self, topic: str, context: str = "") -> dict:

        text = f"{topic} {context}".lower()

        score = 50
        opportunity_type = "general"
        catalysts = []
        watch_items = []

        if any(w in text for w in ["oil", "petroleo", "war", "middle east", "iran", "israel"]):

            score = 81
            opportunity_type = "macro_energy"

            catalysts.extend([
                "Energy supply disruption",
                "Geopolitical escalation",
                "Commodity volatility"
            ])

            watch_items.extend([
                "CL=F",
                "Energy equities",
                "Shipping routes"
            ])

        if any(w in text for w in ["gold", "oro", "inflation", "usd", "dollar weakness"]):

            score = max(score, 76)
            opportunity_type = "hard_assets"

            catalysts.extend([
                "Inflation hedge demand",
                "Dollar weakness",
                "Rates uncertainty"
            ])

            watch_items.extend([
                "GC=F",
                "Gold miners",
                "Real yields"
            ])

        if any(w in text for w in ["ai", "artificial intelligence", "semiconductor", "chips"]):

            score = max(score, 72)
            opportunity_type = "structural_growth"

            catalysts.extend([
                "Compute demand",
                "AI infrastructure growth",
                "Tech narrative momentum"
            ])

            watch_items.extend([
                "NVDA",
                "Semiconductor supply chain"
            ])

        if not catalysts:

            catalysts.append("No asymmetric catalyst identified")
            watch_items.append("Gather more information")

        return {

            "opportunity_score": score,
            "opportunity_type": opportunity_type,
            "catalysts": catalysts,
            "watch_items": watch_items,
            "summary": f"Opportunity engine scored '{topic}' at {score}/100."

        }
