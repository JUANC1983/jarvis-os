from __future__ import annotations

from typing import Any, Dict, List


class StrategicCouncilEngine:
    """
    Strategic council engine.

    Purpose:
    - simulate a high-level executive council
    - collect opinions from multiple specialist lenses
    - detect consensus and disagreement
    - output one executive recommendation
    """

    def __init__(self) -> None:
        self.council_roles = [
            {
                "name": "chief_strategist",
                "lens": "long-term positioning, second-order effects, leverage points",
            },
            {
                "name": "risk_chair",
                "lens": "downside, fragility, hidden exposure, tail risk",
            },
            {
                "name": "capital_allocator",
                "lens": "capital efficiency, opportunity cost, liquidity, sizing",
            },
            {
                "name": "operations_chair",
                "lens": "execution feasibility, complexity, operational friction",
            },
            {
                "name": "life_architect",
                "lens": "impact on time, family, health, energy, long-term quality of life",
            },
        ]

    def _build_opinion(self, role: Dict[str, str], topic: str, context: str) -> Dict[str, Any]:
        text = f"{topic} {context}".lower()
        role_name = role["name"]

        stance = "neutral"
        confidence = 60
        rationale: List[str] = []
        actions: List[str] = []

        if role_name == "chief_strategist":
            if any(w in text for w in ["oil", "war", "middle east", "iran", "israel", "gold", "inflation"]):
                stance = "support_selective_positioning"
                confidence = 78
                rationale = [
                    "Macro context suggests cross-asset repricing risk.",
                    "Energy and hard assets may gain strategic relevance.",
                    "Positioning should favor asymmetric setups, not emotional chasing.",
                ]
                actions = [
                    "Define thesis and invalidation first.",
                    "Prefer staged entry instead of full-size entry.",
                ]
            else:
                rationale = [
                    "No dominant macro asymmetry clearly identified.",
                    "Strategic patience may outperform rushed action.",
                ]
                actions = [
                    "Clarify regime, catalyst, and time horizon.",
                ]

        elif role_name == "risk_chair":
            if any(w in text for w in ["war", "urgent", "emergency", "crisis", "rates", "volatility"]):
                stance = "risk_caution"
                confidence = 84
                rationale = [
                    "Tail-risk probability is elevated.",
                    "Volatility can invalidate good ideas through timing and sizing.",
                    "Capital protection has priority over narrative conviction.",
                ]
                actions = [
                    "Reduce leverage.",
                    "Use explicit downside limits.",
                    "Avoid concentration in one thesis.",
                ]
            else:
                rationale = [
                    "No acute risk cluster detected.",
                ]
                actions = [
                    "Maintain normal risk discipline.",
                ]

        elif role_name == "capital_allocator":
            if any(w in text for w in ["invest", "portfolio", "capital", "wealth", "oil", "gold", "stocks", "crypto"]):
                stance = "allocate_only_if_reward_pays_risk"
                confidence = 76
                rationale = [
                    "Every new position competes against existing and future opportunities.",
                    "Liquidity and optionality matter as much as upside.",
                    "Allocation quality matters more than idea excitement.",
                ]
                actions = [
                    "Compare against best alternative use of capital.",
                    "Size according to conviction and downside.",
                ]
            else:
                rationale = [
                    "Capital deployment case is not yet sufficiently defined.",
                ]
                actions = [
                    "Delay capital commitment until edge is clearer.",
                ]

        elif role_name == "operations_chair":
            if any(w in text for w in ["build", "launch", "system", "automation", "business", "deploy"]):
                stance = "execution_focused"
                confidence = 72
                rationale = [
                    "Execution complexity can destroy otherwise good strategy.",
                    "Simple systems validated early outperform elegant but delayed systems.",
                ]
                actions = [
                    "Reduce dependencies.",
                    "Ship the smallest robust version first.",
                ]
            else:
                rationale = [
                    "Operational execution appears manageable if next steps are explicit.",
                ]
                actions = [
                    "Translate recommendation into concrete task sequence.",
                ]

        elif role_name == "life_architect":
            if any(w in text for w in ["family", "health", "time", "stress", "children", "wife", "energy"]):
                stance = "protect_long_term_life_quality"
                confidence = 82
                rationale = [
                    "The best decision is not only financially correct but life-compatible.",
                    "Energy, relationships, and health are compounding assets too.",
                ]
                actions = [
                    "Reject strategies that create hidden life drag.",
                    "Prefer sustainable, repeatable systems.",
                ]
            else:
                rationale = [
                    "Decision should still be tested against long-term life quality.",
                ]
                actions = [
                    "Check whether this improves or drains time and energy.",
                ]

        return {
            "role": role_name,
            "lens": role["lens"],
            "stance": stance,
            "confidence": confidence,
            "rationale": rationale,
            "recommended_actions": actions,
        }

    def _derive_consensus(self, opinions: List[Dict[str, Any]]) -> Dict[str, Any]:
        stances = [o["stance"] for o in opinions]
        confidence_avg = round(sum(o["confidence"] for o in opinions) / len(opinions), 2) if opinions else 0.0

        caution_votes = sum(1 for s in stances if "risk" in s or "caution" in s)
        support_votes = sum(1 for s in stances if "support" in s or "allocate" in s or "execution" in s)

        if caution_votes >= 2 and support_votes >= 2:
            council_position = "qualified_yes_with_risk_controls"
        elif caution_votes >= 2 and support_votes < 2:
            council_position = "defensive_wait_or_reduce"
        elif support_votes >= 3:
            council_position = "proceed_selectively"
        else:
            council_position = "insufficient_edge"

        return {
            "council_position": council_position,
            "average_confidence": confidence_avg,
        }

    def _executive_recommendation(self, topic: str, context: str, opinions: List[Dict[str, Any]], consensus: Dict[str, Any]) -> Dict[str, Any]:
        position = consensus["council_position"]

        if position == "qualified_yes_with_risk_controls":
            recommendation = (
                "Proceed only in a structured way: staged entry, explicit downside limits, "
                "and continuous validation of the thesis."
            )
            next_steps = [
                "Define exact thesis, catalyst, time horizon, and invalidation.",
                "Limit initial size.",
                "Review whether the opportunity still makes sense under a worse scenario.",
            ]
        elif position == "defensive_wait_or_reduce":
            recommendation = (
                "Do not force action now. Preserve optionality, reduce exposure, and wait for a cleaner setup."
            )
            next_steps = [
                "Avoid full commitment.",
                "Track risk catalysts closely.",
                "Reassess when volatility or uncertainty normalizes.",
            ]
        elif position == "proceed_selectively":
            recommendation = (
                "The council sees a valid opportunity, but execution discipline still matters more than excitement."
            )
            next_steps = [
                "Enter only with defined structure.",
                "Keep risk proportional to conviction.",
                "Do not chase if price has already run too far.",
            ]
        else:
            recommendation = (
                "The council does not yet see enough edge to justify strong action."
            )
            next_steps = [
                "Gather more evidence.",
                "Improve context quality.",
                "Wait for clearer asymmetry.",
            ]

        dissent = []
        for opinion in opinions:
            if opinion["stance"] not in {"neutral", "execution_focused"} and opinion["confidence"] >= 80:
                dissent.append(
                    f"{opinion['role']} emphasized: {opinion['rationale'][0]}"
                )

        return {
            "topic": topic,
            "context": context,
            "executive_recommendation": recommendation,
            "next_steps": next_steps,
            "dissenting_or_strong_views": dissent[:5],
        }

    def deliberate(self, topic: str, context: str = "") -> Dict[str, Any]:
        opinions = [self._build_opinion(role, topic, context) for role in self.council_roles]
        consensus = self._derive_consensus(opinions)
        executive = self._executive_recommendation(topic, context, opinions, consensus)

        return {
            "topic": topic,
            "context": context,
            "council_members": [r["name"] for r in self.council_roles],
            "opinions": opinions,
            "consensus": consensus,
            "executive": executive,
            "summary": (
                f"Strategic council finished deliberation. "
                f"Position: {consensus['council_position']}. "
                f"Average confidence: {consensus['average_confidence']}."
            ),
        }
