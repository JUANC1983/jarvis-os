import numpy as np

class PortfolioBrain:

    def __init__(self):
        pass


    def analyze_portfolio(self, positions):

        total_value = sum([p["value"] for p in positions])

        exposures = {}

        for p in positions:

            asset = p["asset"]
            value = p["value"]

            weight = value / total_value

            exposures[asset] = round(weight * 100,2)

        return {
            "total_value": total_value,
            "exposures_pct": exposures
        }


    def risk_analysis(self, positions):

        weights = np.array([p["value"] for p in positions])

        vol_estimate = np.std(weights)

        if vol_estimate > 10000:
            risk_level = "high"
        elif vol_estimate > 3000:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "portfolio_volatility_estimate": float(vol_estimate),
            "risk_level": risk_level
        }
