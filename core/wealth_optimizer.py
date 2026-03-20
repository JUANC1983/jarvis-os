class WealthOptimizer:
    def optimize(self, capital: float):
        return {
            "capital": capital,
            "allocation": {
                "equities": 40,
                "commodities": 25,
                "real_estate": 20,
                "cash": 15,
            },
            "principle": "Protect downside, preserve optionality, compound intelligently.",
        }
