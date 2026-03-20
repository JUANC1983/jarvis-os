class OpportunityRadarEngine:

    def scan(self, topic: str, context: str = "") -> dict:

        text = f"{topic} {context}".lower()

        opportunities = []
        risks = []
        scenarios = []

        if any(word in text for word in ["war", "guerra", "middle east", "iran", "israel", "oil", "petroleo"]):

            opportunities.extend([
                "Oil upside exposure",
                "Defense-related equities",
                "Shipping and logistics volatility opportunities",
            ])

            risks.extend([
                "Headline-driven reversals",
                "Policy intervention risk",
                "Volatility and correlation spikes",
            ])

            scenarios.extend([
                "Escalation scenario: energy shock",
                "Containment scenario: fast reversal",
            ])

        if any(word in text for word in ["inflation", "inflacion", "gold", "oro", "rates", "tasas", "dollar", "usd"]):

            opportunities.extend([
                "Gold and hard-asset thesis",
                "Commodity-linked positioning",
                "Selective macro hedges",
            ])

            risks.extend([
                "Rate shock repricing",
                "False inflation narrative",
            ])

            scenarios.extend([
                "Sticky inflation scenario",
                "Disinflation with growth scare scenario",
            ])

        if not opportunities:

            opportunities.append("No strong thematic signal detected yet.")
            risks.append("Insufficient context for a strong asymmetric edge.")
            scenarios.append("Base case remains mixed and requires more context.")

        summary = (
            f"Opportunity Radar scanned topic '{topic}'. "
            f"Found {len(opportunities)} opportunity signal(s) and {len(risks)} risk signal(s)."
        )

        return {
            "topic": topic,
            "opportunities": opportunities,
            "risks": risks,
            "scenarios": scenarios,
            "summary": summary,
        }