from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.agent_schema import build_response, degraded


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
        if not (query or "").strip():
            return degraded("Empty query — cannot scan for opportunities", confidence=0.2)
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Opportunity scan failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str) -> Dict[str, Any]:
        text    = (query or "").lower()
        matched = {
            name: data
            for name, data in self._THEMES.items()
            if any(t in text for t in data["triggers"])
        }

        all_opps: List[Dict[str, Any]] = []
        all_risks: List[str] = []

        for theme, data in matched.items():
            all_opps.extend(data.get("opportunities", []))
            all_risks.extend(data.get("risks", []))

        if not matched:
            all_opps  = [{"asset": "Diversified core", "thesis": "No dominant macro theme — maintain base allocation", "timeframe": "ongoing", "conviction": "medium"}]
            all_risks = ["Insufficient context for targeted thesis — broaden query with asset class, geography, or macro theme"]

        high_conviction = sorted(
            all_opps,
            key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("conviction", "low"), 0),
            reverse=True,
        )[:3]

        best = high_conviction[0] if high_conviction else all_opps[0]
        asset    = best.get("asset", "Diversified")
        thesis   = best.get("thesis", "Maintain allocation")
        tf       = best.get("timeframe", "ongoing")
        conv     = best.get("conviction", "medium")

        confidence  = 0.78 if matched else 0.48
        completeness = min(0.5 + len(matched) * 0.15, 1.0)

        action = (
            f"Allocate up to 5% into {asset.split('—')[0].strip()} "
            f"({tf} timeframe). Thesis: {thesis[:80]}. "
            f"Enter on confirmation, staged over 2–4 weeks. Define invalidation trigger first."
        )

        base_signals = [f"Theme: {t}" for t in list(matched.keys())[:3]]
        opp_signals  = [f"Opportunity: {o['asset'].split(',')[0].strip()}" for o in high_conviction[:2]]
        if not matched:
            base_signals = [
                "Theme: none — no macro keyword matched in query",
                f"Fallback: default diversified allocation active (conviction={conv})",
            ]
        all_signals = (base_signals + opp_signals)[:5]
        if len(all_signals) < 2:
            all_signals.append(f"Risk: {all_risks[0][:80]}")

        return build_response(
            confidence=confidence,
            insight=(
                f"Detected {len(matched)} macro theme(s): {', '.join(matched.keys()) or 'none'}. "
                f"{len(all_opps)} opportunities identified. "
                f"Top conviction ({conv}): {asset.split(',')[0].strip()}."
            ),
            risk_level="medium",
            action=action,
            reason=(
                f"Theme matching: {', '.join(matched.keys()) if matched else 'no dominant theme'}. "
                f"High-conviction opportunities ranked by thesis strength. "
                f"Key risk: {all_risks[0] if all_risks else 'narrative reversal'}."
            ),
            signals_used=all_signals,
            data_sources=["macro_theme_matrix_internal", "query_pattern_matching"],
            reasoning_path=[
                "1. Match query against 4-theme macro matrix (geopolitical, inflation, AI/tech, Colombia/LatAm)",
                f"2. Matched themes: {list(matched.keys()) or ['none']}",
                f"3. Extracted {len(all_opps)} opportunities from matched themes",
                "4. Sort by conviction (high > medium > low), select top 3",
                f"5. Top conviction asset: {asset.split(',')[0].strip()} ({conv})",
                f"6. Action: staged 5% allocation with thesis invalidation trigger",
            ],
            data_freshness=1.0,
            data_completeness=completeness,
        )
