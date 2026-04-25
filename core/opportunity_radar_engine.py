from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


class OpportunityRadarEngine:
    """
    Asymmetric opportunity detection engine.
    Scans macro themes, sector rotations, catalyst windows.
    Outputs probability-weighted scenarios with conviction-ranked opportunities.
    """

    _THEMES: Dict[str, Dict[str, Any]] = {
        "geopolitical": {
            "triggers": [
                "war", "guerra", "middle east", "iran", "israel", "taiwan",
                "china", "ukraine", "rusia", "nato", "conflict",
            ],
            "opportunities": [
                {"asset": "Energy — XLE, OXY, CVX",       "thesis": "Supply disruption premium + geopolitical risk bid",           "timeframe": "weeks–months", "conviction": "high"},
                {"asset": "Defense — LMT, RTX, NOC, PLTR", "thesis": "Defense budget expansion is a structural multi-year theme",   "timeframe": "months–years", "conviction": "high"},
                {"asset": "Gold — GLD, IAU",               "thesis": "Safe-haven demand surge — historically reliable in conflict",  "timeframe": "days–weeks",   "conviction": "medium"},
                {"asset": "Shipping — ZIM, MATX",          "thesis": "Re-routing adds cost + reduces capacity = rate spike",        "timeframe": "weeks–months", "conviction": "medium"},
            ],
            "risks": [
                "Rapid de-escalation collapses premium — thesis reversal risk",
                "Policy intervention caps energy prices (SPR release, windfall tax)",
                "Correlation spike: all risk assets sell together in escalation",
            ],
            "scenarios": {
                "bull":   "Escalation: energy and defense surge, safe havens bid strongly",
                "bear":   "De-escalation: positions reverse within days — narrative-driven moves revert fast",
                "base":   "Contained conflict: partial thesis realization, size accordingly",
            },
        },
        "inflation_macro": {
            "triggers": [
                "inflation", "inflacion", "rates", "tasas", "fed", "dollar", "usd",
                "treasury", "bonds", "yields", "commodities",
            ],
            "opportunities": [
                {"asset": "Gold / GLD",                  "thesis": "Real rate collapse = gold positive structural move",           "timeframe": "months–years",  "conviction": "medium"},
                {"asset": "Commodity producers — FCX, VALE", "thesis": "Input price leverage amplifies upside",                   "timeframe": "months",        "conviction": "medium"},
                {"asset": "TIPS / I-bonds",              "thesis": "Inflation-linked income with government guarantee",            "timeframe": "months–years",  "conviction": "high"},
                {"asset": "USD hedge (short COP exposure)", "thesis": "EM currency volatility — structural USD allocation for COP holders", "timeframe": "ongoing", "conviction": "high"},
            ],
            "risks": [
                "Fed credibility restoration triggers rapid disinflation",
                "Demand destruction before supply responds — stagflation tail",
                "Dollar strength headwind for commodity exporters",
            ],
            "scenarios": {
                "bull": "Sticky inflation: hard assets, commodities, short duration — multi-year positioning",
                "bear": "Fast disinflation: growth assets recover sharply, gold under pressure",
                "base": "Grinding inflation with rate plateau — real assets hold, equities volatile",
            },
        },
        "ai_technology": {
            "triggers": [
                "ai", "artificial intelligence", "nvidia", "tech", "semiconductors",
                "chips", "data center", "llm", "model", "openai", "anthropic",
            ],
            "opportunities": [
                {"asset": "NVDA + SMCI",                  "thesis": "AI GPU + infrastructure — 5–10× demand cycle",               "timeframe": "years",        "conviction": "high"},
                {"asset": "Power — VST, CEG, NEE, AMPS",  "thesis": "AI data centers driving 30-year power demand supercycle",    "timeframe": "years",        "conviction": "high"},
                {"asset": "Copper — COPX, FCX",           "thesis": "AI + electrification = structural copper demand 3–5× base",  "timeframe": "years",        "conviction": "medium"},
                {"asset": "Cloud — MSFT, AMZN, GOOGL",    "thesis": "AI monetization through cloud services — durable moat",     "timeframe": "years",        "conviction": "high"},
            ],
            "risks": [
                "Valuation bubble in AI proxies — 2000 dot-com precedent is real",
                "Concentration risk: single theme dominates market cap",
                "Regulatory risk: model regulation, antitrust in AI platforms",
            ],
            "scenarios": {
                "bull": "AI capex cycle continues 5+ years — infrastructure play remains structural",
                "bear": "Bubble burst: 60%+ drawdown in overvalued AI proxies (NVDA in 2022 = -65%)",
                "base": "Consolidation at high valuations — winners separate, losers disappear",
            },
        },
        "colombia_latam": {
            "triggers": [
                "colombia", "latam", "emerging", "mercados emergentes",
                "brazil", "brasil", "mexico", "peru", "bogota", "cop",
            ],
            "opportunities": [
                {"asset": "USD hedge (structural)",          "thesis": "COP structural depreciation — USD allocation is not optional for COP holders", "timeframe": "ongoing",      "conviction": "high"},
                {"asset": "Colombian real assets",           "thesis": "Land and urban real estate historically outperforms COP inflation",            "timeframe": "years",        "conviction": "high"},
                {"asset": "BVC equities — Bancolombia, ISA", "thesis": "Undervalued vs. commodity export base, dividend yield attractive",            "timeframe": "months–years", "conviction": "medium"},
                {"asset": "Private credit / hard assets",    "thesis": "EM volatility premium: real assets beat paper in political uncertainty",       "timeframe": "years",        "conviction": "medium"},
            ],
            "risks": [
                "Political risk: policy uncertainty in Colombia impacts business climate",
                "COP depreciation accelerates beyond hedge",
                "Capital controls — EM tail risk if fiscal situation deteriorates",
            ],
            "scenarios": {
                "bull": "Commodity super-cycle + political stability: Colombian assets re-rate significantly",
                "bear": "Fiscal deterioration + capital flight: COP collapses, hard assets outperform paper",
                "base": "Slow structural growth with COP volatility — real assets + USD allocation optimal",
            },
        },
    }

    def scan(self, topic: str, context: str = "") -> Dict[str, Any]:
        return self.analyze(topic)

    def analyze(self, query: str) -> Dict[str, Any]:
        text    = (query or "").lower()
        matched = {
            name: data
            for name, data in self._THEMES.items()
            if any(t in text for t in data["triggers"])
        }

        all_opps:     List[Dict[str, Any]] = []
        all_risks:    List[str]            = []
        all_scenarios: List[Dict[str, Any]] = []

        for theme, data in matched.items():
            all_opps.extend(data.get("opportunities", []))
            all_risks.extend(data.get("risks", []))
            sc = data.get("scenarios", {})
            all_scenarios.append({
                "theme":     theme,
                "bull_case": sc.get("bull", ""),
                "bear_case": sc.get("bear", ""),
                "base_case": sc.get("base", ""),
            })

        if not matched:
            all_opps = [{
                "asset":       "Diversified — no dominant theme",
                "thesis":      "No single macro theme dominates — broad exposure and base allocation",
                "timeframe":   "ongoing",
                "conviction":  "medium",
            }]
            all_risks    = ["Insufficient context for targeted thesis — specificity improves signal quality"]
            all_scenarios = [{"theme": "base_case", "bull_case": "", "bear_case": "", "base_case": "Mixed signals — maintain base allocation, reduce concentration risk"}]

        high_conviction = sorted(
            all_opps,
            key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("conviction", "low"), 0),
            reverse=True,
        )[:3]

        return {
            "query":              query,
            "themes_detected":    list(matched.keys()),
            "opportunities":      all_opps[:6],
            "highest_conviction": high_conviction,
            "risks":              all_risks[:4],
            "scenarios":          all_scenarios[:3],
            "recommendations": {
                "short_term": [
                    "Position sizing: maximum 5% per speculative theme — conviction doesn't override risk",
                    "Enter on confirmation, not anticipation — narrative moves reverse without warning",
                    f"Monitor catalyst dates: earnings, Fed meeting, geopolitical updates",
                ],
                "mid_term": [
                    "Scale into themes over 2–4 weeks — staged entry reduces timing risk",
                    "Define your thesis invalidation trigger before entering — not after",
                    "Pair speculative positions with protective structure (puts, inverse ETF)",
                ],
                "long_term": [
                    "Structural themes (AI, energy transition, defense) warrant patient, larger positions",
                    "Colombia-specific: hard assets + USD exposure as permanent structural allocation",
                    "Compound winners by trimming at targets and redeploying — don't hold forever",
                ],
            },
            "risk_assessment": {
                "level":         "medium",
                "key_risk":      "Narrative-driven moves revert fast — size for optionality not certainty",
                "correlation":   "Geopolitical assets correlate 1.0 in crisis — not real diversification",
                "position_note": "No single opportunity warrants >5% of total portfolio",
            },
            "confidence":       0.78 if matched else 0.52,
            "decision_clarity": "high" if matched else "low",
            "summary": (
                f"Radar detected {len(matched)} macro theme(s). "
                f"{len(all_opps)} opportunities identified, "
                f"{len(high_conviction)} high-conviction."
            ),
            "source":       "opportunity_radar",
            "generated_at": datetime.utcnow().isoformat(),
        }
