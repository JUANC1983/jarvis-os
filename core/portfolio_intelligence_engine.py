class PortfolioIntelligenceEngine:
    def analyze(self, portfolio: dict):
        assets = portfolio.get("assets", [])
        exposures = {}

        for asset in assets:
            sector = asset.get("sector", "unknown")
            exposures.setdefault(sector, 0)
            exposures[sector] += asset.get("value", 0)

        total = sum(exposures.values())
        allocation = {}

        if total > 0:
            for k, v in exposures.items():
                allocation[k] = round((v / total) * 100, 2)

        return {
            "allocation": allocation,
            "total_value": total,
            "insight": "Portfolio exposure analysis complete",
        }
