from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


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
        text        = (query or "").lower()
        capital     = self._extract_capital(text)
        risk_profile = self._detect_risk_profile(text)
        model       = self._MODELS[risk_profile]

        allocation = self._build_allocation(model, capital)

        return {
            "query":             query,
            "capital":           capital,
            "risk_profile":      risk_profile,
            "model_description": model["description"],
            "target_return":     model["target_return"],
            "max_drawdown_tolerance": model["max_drawdown_tolerance"],
            "allocation":        allocation,
            "core_principle":    "Protect downside first. Preserve optionality. Compound intelligently over time.",
            "colombia_context": {
                "cop_hedge": "Maintain 30–50% of portfolio in USD/EUR — structural COP depreciation hedge",
                "real_assets": "Colombian land and real estate historically beats COP inflation — undervalued entry window exists",
                "tax_note": "Consult contador for optimal entity structure — SAS vs. natural person tax treatment matters",
            },
            "recommendations": {
                "short_term": [
                    "Build 6-month emergency cash runway before deploying into risk assets",
                    "Never concentrate >25% in any single position or asset class",
                    "Review full allocation after any 15%+ drawdown — rebalance with discipline not emotion",
                ],
                "mid_term": [
                    "Rebalance quarterly — discipline consistently beats conviction-based drift",
                    "Add real assets (land, infrastructure) as inflation hedge if <20% allocation",
                    "Tax-optimize: hold growth assets in tax-efficient structures when possible",
                ],
                "long_term": [
                    "Stay invested through market cycles — trying to time markets costs 2–3% annually",
                    "Build geographic diversification: Colombia + US + international exposure",
                    "Legacy planning: assets that compound while you sleep — dividends, real estate cash flow",
                ],
            },
            "risk_assessment": {
                "level": "medium",
                "concentration_risk": "Diversification fails in crises — ensure not over-correlated",
                "liquidity_risk": "Minimum 10% liquid at all times — illiquid assets are a trap in emergencies",
                "currency_risk": "COP exposure requires structural USD hedge — not optional in Colombia",
                "inflation_risk": "Real assets and equities outperform bonds in inflationary regime — adjust accordingly",
            },
            "confidence":       0.82,
            "decision_clarity": "high",
            "source":           "wealth_optimizer",
            "generated_at":     datetime.utcnow().isoformat(),
        }

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
