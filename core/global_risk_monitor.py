from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.agent_schema import build_response, degraded


class GlobalRiskMonitor:
    """
    Multi-domain risk assessment engine.
    Factor identification, probability weighting, protective action set.
    """

    _MATRIX: Dict[str, Dict[str, Any]] = {
        "geopolitical": {
            "triggers": [
                "war", "guerra", "iran", "israel", "middle east", "taiwan",
                "china", "ukraine", "conflict", "nato", "sanctions",
            ],
            "base_score": 72,
            "factors": [
                "Geopolitical escalation → direct energy and commodity shock",
                "Cross-asset volatility: equities, credit, and FX correlate 1.0 in crisis",
                "Shipping and supply chain disruption risk — adds inflation pressure",
                "Safe-haven rotation: USD, JPY, CHF, gold — reduces risk asset returns",
            ],
            "protections": [
                "Reduce leverage below 1× in high-beta positions immediately",
                "Increase cash buffer to 15–20% of portfolio — optionality over returns",
                "Add energy/defense hedge as tail risk insurance",
                "Stop-loss discipline: define exit before crisis, not during it",
            ],
        },
        "macro_financial": {
            "triggers": [
                "inflation", "inflacion", "rates", "fed", "tasas",
                "recession", "credit", "bank", "dollar", "usd",
                "yield", "bonds", "liquidity",
            ],
            "base_score": 60,
            "factors": [
                "Rate regime uncertainty — duration risk in long-dated bonds is severe",
                "Credit market stress — monitor HY spreads as early warning system",
                "Consumer and corporate balance sheet deterioration",
                "USD strength squeezing EM dollar-denominated debt (relevant for Colombia)",
            ],
            "protections": [
                "Avoid long-duration fixed income without yield cushion",
                "Monitor HY credit spreads daily — widening precedes equity selloff by weeks",
                "Reduce EM exposure if DXY strengthens >5% from current level",
                "Quality bias in equities: profitable, low-debt, pricing-power companies",
            ],
        },
        "health": {
            "triggers": [
                "medical", "pain", "symptom", "dolor", "urgent", "emergency",
                "emergencia", "sick", "fever", "fiebre", "ill", "malestar",
            ],
            "base_score": 65,
            "factors": [
                "Unaddressed symptoms compound — delayed diagnosis worsens outcomes",
                "Cognitive and work performance impact from unresolved health issues",
                "Mental bandwidth consumed by health uncertainty affects decision quality",
            ],
            "protections": [
                "Seek qualified medical evaluation — do not self-diagnose symptoms >2 weeks",
                "Document symptom timeline accurately for physician consultation",
                "Emergency services: Colombia 123 / 125 for acute severe presentations",
                "Second medical opinion for any serious or unexpected diagnosis",
            ],
        },
        "operational": {
            "triggers": [
                "business", "empresa", "startup", "legal", "contract",
                "demanda", "compliance", "lawsuit", "contrato", "regulat",
            ],
            "base_score": 52,
            "factors": [
                "Legal and operational exposure creates compounding liability if unmanaged",
                "Contract disputes compound rapidly without clear documentation",
                "Compliance gaps create regulatory risk — particularly in Colombia (DIAN, Supevigilancia)",
                "Key-person dependency is operational risk",
            ],
            "protections": [
                "Document all material business decisions and agreements in writing",
                "Legal review before signing any contract >50M COP in value",
                "Build business continuity — reduce single points of failure",
                "Insurance coverage audit: professional liability + directors & officers",
            ],
        },
        "concentration": {
            "triggers": [
                "portfolio", "allocation", "invest", "single", "concentrated", "bet",
                "position", "holdings", "asset",
            ],
            "base_score": 55,
            "factors": [
                "Concentration >25% in any single position creates catastrophic downside tail",
                "Correlation failure: assets that look uncorrelated converge in crises",
                "Liquidity risk: illiquid positions cannot be exited at fair value under stress",
            ],
            "protections": [
                "Maximum 25% in any single asset, 40% in any single sector",
                "Minimum 10% liquid at all times — never fully deployed",
                "Stress test: what happens to portfolio if largest position drops 50%?",
                "Rebalance: let winners run but trim at portfolio concentration thresholds",
            ],
        },
    }

    def assess(self, topic: str, context: str = "") -> Dict[str, Any]:
        return self.analyze(f"{topic} {context}")

    def analyze(self, query: str) -> Dict[str, Any]:
        if not (query or "").strip():
            return degraded("Empty query — cannot assess risk", confidence=0.2)
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Risk analysis failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str) -> Dict[str, Any]:
        text    = (query or "").lower()
        matched = {
            name: data
            for name, data in self._MATRIX.items()
            if any(t in text for t in data["triggers"])
        }

        if matched:
            base_score      = max(d["base_score"] for d in matched.values())
            compound        = min(base_score + (len(matched) - 1) * 6, 100)
            all_factors     = [f for d in matched.values() for f in d["factors"]]
            all_protections = [p for d in matched.values() for p in d["protections"]]
            dominant        = max(matched.keys(), key=lambda k: matched[k]["base_score"])
            completeness    = min(0.9 + len(matched) * 0.05, 1.0)
        else:
            compound        = 40
            all_factors     = [
                "No critical risk cluster detected in query context",
                "Baseline monitoring: no geopolitical, macro, health, operational, or concentration keywords matched",
            ]
            all_protections = [
                "Maintain baseline risk discipline: diversify, hold 10% cash, define stop-loss on every position",
                "Regular portfolio and life audit — risk grows silently",
            ]
            dominant        = "general"
            completeness    = 0.55

        if compound >= 85:
            level = "high"
        elif compound >= 50:
            level = "medium"
        else:
            level = "low"

        confidence   = round(min(compound / 100 * 0.95 + 0.05, 0.93), 3)
        top_action   = all_protections[0] if all_protections else "Maintain current risk discipline"

        return build_response(
            confidence=confidence,
            insight=(
                f"Risk score {compound}/100 across {len(matched)} domain(s): "
                f"{', '.join(matched.keys()) or 'general'}. "
                f"Dominant risk: {dominant}. "
                f"{len(all_factors)} active risk factor(s) identified."
            ),
            risk_level=level,
            action=top_action,
            reason=(
                f"Score derived from {len(matched)} matched risk matrix domain(s). "
                f"Compound effect of multiple domains adds 6pts each. "
                f"Threshold: ≥85→high, ≥50→medium, <50→low."
            ),
            signals_used=all_factors[:4],
            data_sources=["risk_matrix_internal", "query_pattern_matching"],
            reasoning_path=[
                "1. Parse query against 5-domain risk matrix (geopolitical, macro, health, operational, concentration)",
                f"2. Matched domains: {list(matched.keys()) or ['none']}",
                f"3. Base score from dominant domain: {base_score if matched else 40}",
                f"4. Compound adjustment: +{(len(matched)-1)*6 if len(matched)>1 else 0}pts for multi-domain overlap",
                f"5. Final score: {compound}/100 → risk_level={level}",
                f"6. Primary protective action: {top_action[:80]}",
            ],
            data_freshness=1.0,
            data_completeness=completeness,
        )

    def _short_recs(self, level: str, domains: List[str]) -> List[str]:
        if level == "critical":
            return [
                "IMMEDIATE ACTION — escalate to appropriate specialist without delay",
                "Do not minimize or rationalize critical risk signals",
            ]
        if level == "high":
            return [
                "Reduce exposure to the highest-risk element today — not this week, today",
                "Activate protective measures from the list — do not wait for confirmation",
                "Define your explicit trigger for further escalation",
            ]
        return [
            "Monitor identified risk factors over next 7 days",
            "Implement protective measures as standard precaution",
            "Define your tolerance threshold explicitly — know your stop before you need it",
        ]
