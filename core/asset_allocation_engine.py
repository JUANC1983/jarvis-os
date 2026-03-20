class AssetAllocationEngine:

    def recommend(self,risk_profile):

        if risk_profile=="aggressive":

            return {
                "equities":60,
                "crypto":15,
                "commodities":10,
                "real_estate":10,
                "cash":5
            }

        if risk_profile=="balanced":

            return {
                "equities":45,
                "commodities":15,
                "real_estate":15,
                "bonds":15,
                "cash":10
            }

        return {
            "bonds":40,
            "equities":30,
            "real_estate":15,
            "gold":10,
            "cash":5
        }
