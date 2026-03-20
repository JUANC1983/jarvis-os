class WealthStrategist:

    def strategy(self,goal):

        goal=goal.lower()

        if "wealth" in goal or "rich" in goal:

            return {
                "focus":[
                    "equity compounding",
                    "global opportunities",
                    "private investments",
                    "asymmetric bets"
                ]
            }

        if "income" in goal:

            return {
                "focus":[
                    "dividend stocks",
                    "real estate",
                    "cash flow assets"
                ]
            }

        return {
            "focus":[
                "balanced portfolio",
                "risk control",
                "long term growth"
            ]
        }
