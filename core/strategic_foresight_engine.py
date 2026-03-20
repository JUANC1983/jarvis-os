from __future__ import annotations

from typing import Any, Dict, List


class StrategicForesightEngine:
    """
    Strategic foresight engine.

    Purpose:
    - simulate plausible future scenarios
    - detect second-order effects
    - estimate risk posture
    - recommend strategic action
    """

    def __init__(self) -> None:
        self.base_scenarios = {
            "oil_geopolitics": [
                {
                    "name": "energy_shock_escalates",
                    "probability": 0.35,
                    "impact": "high",
                    "time_horizon": "days_to_weeks",
                    "effects": [
                        "Oil spikes",
                        "Inflation expectations rise",
                        "Volatility increases",
                        "Shipping and airlines pressured",
                        "Energy producers benefit",
                    ],
                },
                {
                    "name": "contained_tension",
                    "probability": 0.40,
                    "impact": "medium",
                    "time_horizon": "days_to_weeks",
                    "effects": [
                        "Oil remains bid but controlled",
                        "Markets stay headline-sensitive",
                        "Selective opportunities dominate",
                    ],
                },
                {
                    "name": "de_escalation_relief",
                    "probability": 0.25,
                    "impact": "medium",
                    "time_horizon": "days",
                    "effects": [
                        "Oil retraces quickly",
                        "Risk assets rebound",
                        "Gold may soften",
                    ],
                },
            ],
            "rates_inflation": [
                {
                    "name": "higher_for_longer",
                    "probability": 0.40,
                    "impact": "high",
                    "time_horizon": "weeks_to_months",
                    "effects": [
                        "Pressure on long-duration assets",
                        "Dollar remains firm",
                        "Valuation compression risk",
                    ],
                },
                {
                    "name": "policy_relief",
                    "probability": 0.25,
                    "impact": "high",
                    "time_horizon": "weeks_to_months",
                    "effects": [
                        "Growth assets re-rate",
                        "Liquidity improves",
                        "Risk appetite expands",
                    ],
                },
                {
                    "name": "mixed_macro_chop",
                    "probability": 0.35,
                    "impact": "medium",
                    "time_horizon": "weeks",
                    "effects": [
                        "Choppy conditions",
                        "Narrative rotations",
                        "Need for selective entries",
                    ],
                },
            ],
            "default": [
                {
                    "name": "base_case",
                    "probability": 0.50,
                    "impact": "medium",
                    "time_horizon": "weeks",
                    "effects": [
                        "Moderate uncertainty",
                        "Selective opportunities only",
                    ],
                },
                {
                    "name": "upside_surprise",
                    "probability": 0.20,
                    "impact": "medium",
                    "time_horizon": "days_to_weeks",
                    "effects": [
                        "Faster upside repricing",
                        "Need to avoid being too defensive",
                    ],
                },
                {
                    "name": "downside_surprise",
                    "probability": 0.30,
                    "impact": "high",
                    "time_horizon": "days_to_weeks",
                    "effects": [
                        "Risk-off move",
                        "Capital preservation becomes priority",
                    ],
                },
            ],
        }

    def _classify_topic(self, topic: str, context: str) -> str:
        text = f"{topic} {context}".lower()

        if any(w in text for w in ["oil", "petroleo", "middle east", "iran", "israel", "war", "energy"]):
            return "oil_geopolitics"

        if any(w in text for w in ["rates", "fed", "inflation", "yield", "dollar", "usd"]):
            return "rates_inflation"

        return "default"

    def _scenario_set(self, topic: str, context: str) -> List[Dict[str, Any]]:
        key = self._classify_topic(topic, context)
        return self.base_scenarios.get(key, self.base_scenarios["default"])

    def _second_order_effects(self, scenarios: List[Dict[str, Any]]) -> List[str]:
        effects: List[str] = []

        for scenario in scenarios:
            joined = " ".join(scenario.get("effects", [])).lower()

            if "oil spikes" in joined:
                effects.append("Higher energy costs can pressure margins across transport, logistics, and consumers.")
            if "inflation expectations rise" in joined:
                effects.append("Inflation repricing can change rates expectations and hurt valuation-sensitive assets.")
            if "volatility increases" in joined:
                effects.append("Good ideas can still fail if position sizing and timing are poor.")
            if "liquidity improves" in joined:
                effects.append("Improved liquidity can create upside asymmetry in growth and higher-beta assets.")
            if "risk-off move" in joined:
                effects.append("Cash, hedges, and optionality become more valuable than forced conviction.")

        deduped = []
        seen = set()
        for effect in effects:
            if effect not in seen:
                deduped.append(effect)
                seen.add(effect)

        return deduped[:8]

    def _strategic_posture(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        high_weight = sum(s["probability"] for s in scenarios if s["impact"] == "high")
        medium_weight = sum(s["probability"] for s in scenarios if s["impact"] == "medium")

        if high_weight >= 0.45:
            posture = "defensive_selective"
            actions = [
                "Protect capital first.",
                "Use staged entries only.",
                "Keep liquidity available.",
                "Prefer asymmetric opportunities over broad exposure.",
            ]
        elif high_weight >= 0.25:
            posture = "balanced_selective"
            actions = [
                "Take only high-conviction opportunities.",
                "Avoid concentration in one narrative.",
                "Demand explicit invalidation and downside control.",
            ]
        else:
            posture = "measured_offense"
            actions = [
                "Selective offense is acceptable.",
                "Do not chase extended price action.",
                "Use structure and timing, not emotion.",
            ]

        return {
            "posture": posture,
            "actions": actions,
            "high_impact_probability": round(high_weight, 2),
            "medium_impact_probability": round(medium_weight, 2),
        }

    def _asset_implications(self, topic: str, context: str, posture: str) -> Dict[str, Any]:
        text = f"{topic} {context}".lower()

        beneficiaries: List[str] = []
        pressured: List[str] = []
        hedges: List[str] = []

        if any(w in text for w in ["oil", "energy", "war", "middle east", "iran", "israel"]):
            beneficiaries.extend(["Energy producers", "Oil-linked assets", "Some hard assets"])
            pressured.extend(["Airlines", "Transport", "Rate-sensitive growth if inflation reprices"])
            hedges.extend(["Gold", "Cash", "Defined-risk structures"])

        if any(w in text for w in ["rates", "inflation", "fed", "yield", "dollar"]):
            beneficiaries.extend(["Short-duration exposure", "Selective value", "Dollar-linked resilience"])
            pressured.extend(["Long-duration growth", "Rate-sensitive names"])
            hedges.extend(["Cash", "Hard assets", "Selective defensive sectors"])

        if not beneficiaries:
            beneficiaries.append("Selective high-quality assets with strong structure")
        if not pressured:
            pressured.append("Weak balance-sheet or overextended assets")
        if not hedges:
            hedges.append("Cash and explicit downside controls")

        return {
            "beneficiaries": beneficiaries[:6],
            "pressured_assets": pressured[:6],
            "hedges": hedges[:6],
            "posture_alignment": posture,
        }

    def simulate(self, topic: str, context: str = "") -> Dict[str, Any]:
        scenarios = self._scenario_set(topic, context)
        posture = self._strategic_posture(scenarios)
        second_order = self._second_order_effects(scenarios)
        asset_map = self._asset_implications(topic, context, posture["posture"])

        return {
            "topic": topic,
            "context": context,
            "scenario_family": self._classify_topic(topic, context),
            "scenarios": scenarios,
            "second_order_effects": second_order,
            "recommended_posture": posture["posture"],
            "recommended_actions": posture["actions"],
            "probability_profile": {
                "high_impact_probability": posture["high_impact_probability"],
                "medium_impact_probability": posture["medium_impact_probability"],
            },
            "asset_implications": asset_map,
            "executive_summary": (
                f"Strategic foresight completed for '{topic}'. "
                f"Recommended posture: {posture['posture']}. "
                f"Focus on second-order effects and capital protection before aggressive positioning."
            ),
        }
