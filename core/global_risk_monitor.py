from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


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
        text    = (query or "").lower()
        matched = {
            name: data
            for name, data in self._MATRIX.items()
            if any(t in text for t in data["triggers"])
        }

        if matched:
            base_score = max(d["base_score"] for d in matched.values())
            compound   = min(base_score + (len(matched) - 1) * 6, 100)
            all_factors    = [f for d in matched.values() for f in d["factors"]]
            all_protections = [p for d in matched.values() for p in d["protections"]]
        else:
            compound = 40
            all_factors    = ["No critical risk cluster detected in query context"]
            all_protections = [
                "Maintain baseline risk discipline",
                "Regular portfolio and life audit — risk grows silently",
            ]

        if compound >= 85:
            level = "critical"
        elif compound >= 70:
            level = "high"
        elif compound >= 50:
            level = "medium"
        else:
            level = "low"

        return {
            "query":        query,
            "risk_domains": list(matched.keys()),
            "risk_score":   compound,
            "risk_level":   level,
            "risk_factors": all_factors[:6],
            "protections":  all_protections[:5],

            "recommendations": {
                "short_term": self._short_recs(level, list(matched.keys())),
                "mid_term": [
                    "Build systematic risk monitoring — automate alerts for key thresholds",
                    "Pre-mortem: assume the worst outcome — what does the path there look like?",
                    "Diversify across genuinely uncorrelated risk buckets",
                ],
                "long_term": [
                    "Antifragility over resilience: systems that gain from disorder",
                    "Barbell strategy: very safe + high-optionality, avoid the middle",
                    "Annual comprehensive risk audit: financial, legal, health, operational",
                ],
            },
            "risk_assessment": {
                "level":       level,
                "score":       compound,
                "compound_risk": len(matched) > 1,
                "compound_note": (
                    "Multiple risk domains detected — correlation between them amplifies total risk"
                    if len(matched) > 1 else None
                ),
                "dominant_domain": (
                    max(matched.keys(), key=lambda k: matched[k]["base_score"])
                    if matched else "general"
                ),
            },
            "confidence":       0.83,
            "decision_clarity": "high",
            "summary": (
                f"Risk score {compound}/100 ({level}). "
                f"{len(all_factors)} factors across {len(matched)} domain(s)."
            ),
            "source":       "global_risk_monitor",
            "generated_at": datetime.utcnow().isoformat(),
        }

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
