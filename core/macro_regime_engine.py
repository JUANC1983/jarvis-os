class MacroRegimeEngine:
    def analyze(self, topic: str, context: str = "") -> dict:
        text = f"{topic} {context}".lower()

        regime = "mixed_transition"
        characteristics = []
        playbook = []

        if any(w in text for w in ["war", "oil", "middle east", "iran", "israel"]):
            regime = "geopolitical_energy_stress"
            characteristics = [
                "Energy sensitivity high",
                "Inflationary pressure possible",
                "Cross-asset volatility elevated",
            ]
            playbook = [
                "Stress test energy exposure",
                "Review oil, defense, and volatility trades",
                "Protect downside before chasing momentum",
            ]

        elif any(w in text for w in ["inflation", "inflacion", "usd", "gold"]):
            regime = "inflation_hard_asset_support"
            characteristics = [
                "Hard assets favored",
                "Duration risk elevated",
                "Real-asset narratives strengthen",
            ]
            playbook = [
                "Review gold and commodity allocations",
                "Watch real yields and policy expectations",
                "Avoid over-concentration in one inflation hedge",
            ]

        elif any(w in text for w in ["rate cuts", "liquidity", "growth", "soft landing"]):
            regime = "liquidity_growth_support"
            characteristics = [
                "Risk appetite can improve",
                "Growth assets may re-rate",
                "Narrative sensitivity high",
            ]
            playbook = [
                "Review growth exposure and valuations",
                "Separate narrative from real cash-flow quality",
                "Keep hedges in case growth disappoints",
            ]

        summary = f"Macro regime engine classified the current context as '{regime}'."

        return {
            "regime": regime,
            "characteristics": characteristics,
            "playbook": playbook,
            "summary": summary,
        }
