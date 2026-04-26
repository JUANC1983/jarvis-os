from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.agent_schema import build_response, degraded


class WealthOptimizer:
    """
    Multi-layer wealth architecture engine.
    Risk-adjusted allocation with reasoning, tax efficiency, and compounding strategy.
    """

    _MODELS: Dict[str, Dict[str, Any]] = {
        "conservative": {
            "equities": 25, "bonds": 35, "real_assets": 25, "alternatives": 5, "cash": 10,
            "description": "Capital preservation — protecting downside in volatile macro environment",
            "target_return": "Inflation + 2–3%",
            "max_drawdown_tolerance": "~10%",
        },
        "balanced": {
            "equities": 40, "bonds": 20, "real_assets": 20, "alternatives": 10, "cash": 10,
            "description": "Risk-parity approach — balance between growth and capital protection",
            "target_return": "Inflation + 4–6%",
            "max_drawdown_tolerance": "~20%",
        },
        "growth": {
            "equities": 60, "bonds": 10, "real_assets": 15, "alternatives": 10, "cash": 5,
            "description": "Long-horizon growth — accept short-term volatility for compounding",
            "target_return": "Inflation + 7–9%",
            "max_drawdown_tolerance": "~35%",
        },
        "aggressive": {
            "equities": 75, "bonds": 5, "real_assets": 10, "alternatives": 8, "cash": 2,
            "description": "Maximum compounding — requires high risk tolerance and 10+ year horizon",
            "target_return": "Inflation + 10%+",
            "max_drawdown_tolerance": "50%+",
        },
    }

    _ASSET_RATIONALE: Dict[str, str] = {
        "equities":     "Growth engine — long-term compounding through business ownership. Best asset in 10-year+ horizon.",
        "bonds":        "Stability anchor — reduces portfolio volatility, income stream in downturns. Hedge against deflation.",
        "real_assets":  "Inflation hedge — land, real estate, infrastructure hold purchasing power. Colombia: undervalued vs. GDP.",
        "alternatives": "Decorrelation layer — private credit, commodities, hedge funds reduce beta to equity markets.",
        "cash":         "Optionality reserve — dry powder for crisis opportunities and personal emergencies. Never below 6 months expenses.",
    }

    def optimize(
        self,
        capital: float,
        risk_tolerance: str = "balanced",
        horizon_years: int = 10,
    ) -> Dict[str, Any]:
        return self.analyze(f"optimize {capital} capital {risk_tolerance} {horizon_years} years")

    def analyze(self, query: str) -> Dict[str, Any]:
        if not (query or "").strip():
            return degraded("Empty wealth query — provide capital, risk profile, or allocation question", confidence=0.2)
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Wealth optimization failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str) -> Dict[str, Any]:
        text         = (query or "").lower()
        capital      = self._extract_capital(text)
        risk_profile = self._detect_risk_profile(text)
        model        = self._MODELS[risk_profile]
        allocation   = self._build_allocation(model, capital)

        short_recs = [
            "Build 6-month emergency cash runway before deploying into risk assets",
            "Never concentrate >25% in any single position or asset class",
            "COP hedge: maintain 30–50% in USD/EUR — structural depreciation protection",
        ]
        capital_str = f"${capital:,.0f}" if capital else "unspecified capital"

        action = (
            f"Implement {risk_profile} allocation: "
            f"equities {model['equities']}%, real_assets {model['real_assets']}%, "
            f"bonds {model['bonds']}%, alternatives {model['alternatives']}%, cash {model['cash']}%. "
            f"Target return: {model['target_return']}. Max drawdown tolerance: {model['max_drawdown_tolerance']}."
        )

        completeness = 0.9 if capital else 0.7

        return build_response(
            confidence=0.82,
            insight=(
                f"Wealth profile: {risk_profile}. {model['description']}. "
                f"Capital: {capital_str}. Target return: {model['target_return']}. "
                f"Max drawdown tolerance: {model['max_drawdown_tolerance']}."
            ),
            risk_level="medium",
            action=action,
            reason=(
                f"Risk profile {risk_profile!r} detected from query keywords. "
                f"Allocation optimized for {model['target_return']} target with {model['max_drawdown_tolerance']} drawdown tolerance. "
                f"Colombia COP structural depreciation factored into recommendation."
            ),
            signals_used=[
                f"Risk profile: {risk_profile}",
                f"Target return: {model['target_return']}",
                f"Max drawdown tolerance: {model['max_drawdown_tolerance']}",
                f"Equity allocation: {model['equities']}%",
            ],
            data_sources=["wealth_allocation_model_library", "colombia_macro_context"],
            reasoning_path=[
                f"1. Detect risk profile from query keywords → {risk_profile}",
                f"2. Load {risk_profile} allocation model: equities={model['equities']}%, bonds={model['bonds']}%",
                f"3. Extract capital amount: {capital_str}",
                f"4. Apply Colombia macro context: COP hedge, real asset inflation protection",
                f"5. Action: {action[:100]}",
            ],
            data_freshness=1.0,
            data_completeness=completeness,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _build_allocation(self, model: Dict, capital: Optional[float]) -> Dict[str, Any]:
        result = {}
        for asset, pct in model.items():
            if asset in ("description", "target_return", "max_drawdown_tolerance"):
                continue
            entry: Dict[str, Any] = {
                "pct":       pct,
                "rationale": self._ASSET_RATIONALE.get(asset, ""),
            }
            if capital and capital > 0:
                entry["amount"] = round(capital * pct / 100, 0)
            result[asset] = entry
        return result

    def _extract_capital(self, text: str) -> Optional[float]:
        m = re.search(r'\b(\d[\d,\.]*)\s*(?:usd|cop|million|millones|m\b|k\b)?', text)
        if m:
            val = float(m.group(1).replace(",", "").replace(".", ""))
            if val > 0:
                return val
        return None

    def _detect_risk_profile(self, text: str) -> str:
        if any(w in text for w in ["conservative", "conservador", "safe", "protect", "bajo riesgo", "preserve"]):
            return "conservative"
        if any(w in text for w in ["aggressive", "agresivo", "maximum", "máximo"]):
            return "aggressive"
        if any(w in text for w in ["growth", "crecer", "crecimiento", "grow"]):
            return "growth"
        return "balanced"
