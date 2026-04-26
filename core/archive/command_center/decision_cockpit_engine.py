class DecisionCockpitEngine:
    def evaluate(self, topic: str, domain: str, risk_payload: dict, opportunity_payload: dict, council_payload: dict) -> dict:
        risk_score = risk_payload.get("risk_score", 50)
        opp_score = opportunity_payload.get("opportunity_score", 50)

        if opp_score >= 75 and risk_score <= 65:
            stance = "selective_offense"
        elif opp_score >= 70 and risk_score >= 70:
            stance = "high_potential_but_high_risk"
        elif opp_score < 60 and risk_score > 70:
            stance = "defensive"
        else:
            stance = "balanced"

        next_steps = []
        if stance == "selective_offense":
            next_steps.extend([
                "Define exact thesis, sizing, and invalidation.",
                "Confirm timing with real market data.",
                "Preserve downside discipline while exploiting opportunity.",
            ])
        elif stance == "high_potential_but_high_risk":
            next_steps.extend([
                "Treat as advanced setup only.",
                "Reduce size and tighten downside controls.",
                "Validate whether risk is being paid enough.",
            ])
        elif stance == "defensive":
            next_steps.extend([
                "Avoid aggressive exposure.",
                "Increase optionality and liquidity.",
                "Wait for a cleaner setup or better information.",
            ])
        else:
            next_steps.extend([
                "Proceed only with structured validation.",
                "Clarify time horizon and constraints.",
                "Balance upside with strategic resilience.",
            ])

        return {
            "topic": topic,
            "domain": domain,
            "recommended_stance": stance,
            "risk_score": risk_score,
            "opportunity_score": opp_score,
            "consensus": council_payload.get("consensus", ""),
            "next_steps": next_steps,
            "summary": f"Decision cockpit recommends '{stance}' for '{topic}'."
        }
