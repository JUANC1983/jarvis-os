from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List

from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.market_data_engine import MarketDataEngine
from core.market_intelligence_engine import MarketIntelligenceEngine
from core.global_market_intelligence_system import GlobalMarketIntelligenceSystem
from core.news_intelligence_engine import NewsIntelligenceEngine
from core.opportunity_discovery_engine import OpportunityDiscoveryEngine
from core.opportunity_scoring_engine import OpportunityScoringEngine
from core.decision_engine import DecisionEngine
from core.product_brain import ProductBrain


class ProductBrainPro:

    def __init__(self) -> None:

        self.orchestrator = AgentOrchestratorPro()

        self.market_data = MarketDataEngine()
        self.market_intel = MarketIntelligenceEngine()
        self.global_intel = GlobalMarketIntelligenceSystem()
        self.news_engine = NewsIntelligenceEngine()
        self.opportunity_engine = OpportunityDiscoveryEngine()
        self.opportunity_scoring = OpportunityScoringEngine()
        self.decision_engine = DecisionEngine()
        self.brain = ProductBrain()   # reuse existing scored recommendations

    def analyze_asset(self, symbol: str) -> Dict[str, Any]:

        symbol = symbol.upper().strip()

        quotes = self.market_data.get_quotes([symbol])
        quote = quotes[0] if quotes else {}

        micro = self.market_intel.analyze_symbol(symbol)
        macro = self.global_intel.scan()
        news = self.news_engine.fetch_news()
        opportunities = self.opportunity_engine.scan()

        trader = self.orchestrator.execute_trader(symbol)

        opportunity_context = self.opportunity_scoring.score(symbol)

        trader_score = trader.get("setup_score", 0) or 0
        opportunity_score = opportunity_context.get("opportunity_score", 50)

        macro_state = macro.get("volatility_and_liquidity_regime", {})
        volatility = macro_state.get("volatility_regime", "neutral")

        macro_adjustment = 0
        if volatility == "stress":
            macro_adjustment = -10
        elif volatility == "calm":
            macro_adjustment = +5

        final_score = int(
            (trader_score * 0.6) +
            (opportunity_score * 0.3) +
            macro_adjustment
        )

        final_score = max(0, min(100, final_score))

        decision = self.decision_engine.evaluate(
            f"{symbol} score {final_score}"
        )

        return {
            "symbol": symbol,
            "price": quote.get("price"),
            "change_pct": quote.get("change_pct"),
            "setup_score": final_score,
            "trader": trader,
            "micro": micro,
            "macro_summary": macro.get("executive_summary"),
            "news_count": len(news),
            "opportunity": opportunity_context,
            "decision": decision,
            "confidence": decision.get("score"),
            "source": "product_brain_pro"
        }

    def recommendations(self) -> Dict[str, Any]:

        symbols = [
            "NVDA", "AAPL", "MSFT", "AMZN", "META",
            "TSLA", "PLTR", "COIN", "SMCI",
            "XOM", "CVX", "BTC", "ETH"
        ]

        results: List[Dict[str, Any]] = []

        for s in symbols:
            try:
                r = self.analyze_asset(s)
                if r.get("price") is not None:
                    results.append(r)
            except Exception:
                continue

        results = sorted(results, key=lambda x: x["setup_score"], reverse=True)

        return {
            "items": results[:10],
            "engine": "PRO",
        }

    # ------------------------------------------------------------------ #
    # AUTO SCAN — parallel market intelligence + structured actions        #
    # ------------------------------------------------------------------ #
    def auto_scan(self) -> Dict[str, Any]:
        """
        Full JARVIS auto-intelligence run.

        Runs three data sources in parallel to stay under ~12s total:
          1. brain.recommendations()               — per-symbol scored setups
          2. global_intel.volatility_and_liquidity_regime() — VIX/TNX/DXY regime
          3. opportunity_engine.scan()             — momentum + deep-value signals
          4. global_intel.sector_rotation()        — sector leaders/laggards

        Derives:
          - summary    : one-sentence macro + setup narrative
          - actions    : ≤5 specific, data-driven action strings
          - confidence : weighted score from real data
        """
        # --- parallel execution ---
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        def _run(key: str, fn):
            try:
                results[key] = fn()
            except Exception as e:
                errors[key] = str(e)

        tasks = {
            "recs":      lambda: self.brain.recommendations(),
            "vol":       lambda: self.global_intel.volatility_and_liquidity_regime(),
            "opp":       lambda: self.opportunity_engine.scan(),
            "sectors":   lambda: self.global_intel.sector_rotation(),
            "risk":      lambda: self.global_intel.risk_matrix(),
        }

        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {pool.submit(_run, k, fn): k for k, fn in tasks.items()}
            for f in as_completed(futures, timeout=18):
                pass  # _run writes directly into results

        # --- extract real data ---
        recs_items: List[Dict[str, Any]] = (results.get("recs") or {}).get("items", [])[:5]
        vol        = results.get("vol") or {}
        opp_ideas  = results.get("opp") or []
        sectors    = results.get("sectors") or {}
        risk       = results.get("risk") or {}

        vol_regime   = vol.get("volatility_regime", "neutral")
        liquidity    = vol.get("macro_liquidity_state", "neutral")
        rates_regime = vol.get("rates_regime", "neutral")
        risk_flags   = risk.get("risk_flags", [])
        opp_flags    = risk.get("opportunity_flags", [])
        leaders      = [s["symbol"] for s in sectors.get("leaders", [])]
        laggards     = [s["symbol"] for s in sectors.get("laggards", [])]

        # momentum ideas from OpportunityDiscoveryEngine
        momentum_syms = [i["symbol"] for i in opp_ideas if i.get("type") == "momentum"]
        value_syms    = [
            i for i in opp_ideas if i.get("type") == "deep_value"
        ]

        # --- derive confidence from real scores ---
        if recs_items:
            raw_scores = [r.get("setup_score", 50) for r in recs_items]
            base_conf = round(sum(raw_scores) / len(raw_scores) / 100, 3)
        else:
            base_conf = 0.50

        # penalise for macro stress
        if vol_regime == "stress":
            base_conf = round(base_conf * 0.80, 3)
        elif vol_regime == "calm" and liquidity == "supportive":
            base_conf = round(min(base_conf * 1.08, 0.97), 3)

        if rates_regime == "rates_up_pressure":
            base_conf = round(base_conf * 0.93, 3)

        confidence = round(max(0.20, min(0.97, base_conf)), 2)

        # --- build actions from real data ---
        actions: List[str] = []

        for item in recs_items:
            sym   = item.get("symbol", "")
            score = item.get("setup_score", 0)
            light = item.get("traffic_light", "red")
            rec   = item.get("friendly_recommendation", "")
            price = item.get("price_now") or item.get("price")

            price_str = f" @ {price}" if price else ""

            if light == "green" and score >= 80:
                action = f"Buy {sym}{price_str} on pullback — score {score}. {rec}"
            elif light == "green" and score >= 60:
                action = f"Watch {sym}{price_str} for entry — score {score}. {rec}"
            elif light == "yellow":
                action = f"Hold off on {sym} — setup not clean yet (score {score})."
            else:
                action = f"Avoid {sym} — score {score}, adverse setup."

            actions.append(action.strip())

        # inject macro-level action if risk matrix has specific flags
        for flag in opp_flags[:1]:
            actions.append(f"Macro opportunity: {flag}")
        for flag in risk_flags[:1]:
            actions.append(f"Risk alert: {flag} Reduce exposure accordingly.")

        # add deep-value special mention if any
        if value_syms:
            v = value_syms[0]
            actions.append(
                f"Deep-value signal on {v['symbol']} "
                f"({round(v['drawdown_pct'], 1)}% off highs) — accumulate in tranches if thesis holds."
            )

        # cap at 5
        actions = actions[:5]

        if not actions:
            actions = ["No high-conviction setups detected right now. Stay patient and protect capital."]

        # --- build summary ---
        summary = self._build_summary(
            vol_regime, liquidity, rates_regime,
            recs_items, leaders, opp_flags, risk_flags,
        )

        return {
            "summary":    summary,
            "actions":    actions,
            "confidence": confidence,
            "generated_at": datetime.utcnow().isoformat(),
            # extra context useful for dashboard display
            "meta": {
                "vol_regime":   vol_regime,
                "liquidity":    liquidity,
                "top_sectors":  leaders[:2],
                "weak_sectors": laggards[:2],
                "signals_used": len(recs_items),
            },
        }

    def _build_summary(
        self,
        vol_regime: str,
        liquidity: str,
        rates_regime: str,
        recs_items: List[Dict[str, Any]],
        sector_leaders: List[str],
        opp_flags: List[str],
        risk_flags: List[str],
    ) -> str:
        """Compose a one-sentence macro + setup narrative from real data only."""
        parts: List[str] = []

        # macro backdrop
        if vol_regime == "stress":
            parts.append("Volatility stress elevated")
        elif vol_regime == "calm":
            parts.append("Low-volatility environment")
        else:
            parts.append("Neutral volatility backdrop")

        if liquidity == "supportive":
            parts.append("with supportive liquidity")
        elif liquidity == "tightening_or_stressed":
            parts.append("with tightening macro liquidity")
        else:
            parts.append("with mixed liquidity conditions")

        if rates_regime == "rates_up_pressure":
            parts.append("and rising rate pressure")
        elif rates_regime == "rates_relief":
            parts.append("and easing rate pressure")

        # setup quality
        green = [r for r in recs_items if r.get("traffic_light") == "green"]
        if len(green) >= 3:
            top_names = ", ".join(r["symbol"] for r in green[:3])
            parts.append(f"— {len(green)} green setups led by {top_names}")
        elif green:
            parts.append(f"— limited green setups: {green[0]['symbol']}")
        else:
            parts.append("— no clean setups currently")

        # sector colour
        if sector_leaders:
            parts.append(f"with strength in {'/'.join(sector_leaders[:2])}")

        # override tone if risk flags dominate
        if risk_flags and not opp_flags:
            parts.append("Defensive posture recommended.")

        return " ".join(parts) + "."

    def _compute_final_score(
        self,
        trader_score: float,
        micro: dict,
        macro_summary: str,
        opportunity: dict
    ) -> float:

        micro_score = 50

        trend = micro.get("trend")
        momentum = micro.get("momentum")

        if trend == "bullish":
            micro_score += 25
        elif trend == "bearish":
            micro_score -= 25

        if momentum == "strong":
            micro_score += 15
        elif momentum == "neutral":
            micro_score += 0
        else:
            micro_score -= 10

        micro_score = max(0, min(100, micro_score))

        macro_score = 50
        text = (macro_summary or "").lower()

        if "stress" in text or "tightening" in text:
            macro_score -= 15

        if "supportive" in text:
            macro_score += 15

        macro_score = max(0, min(100, macro_score))

        opportunity_score = opportunity.get("opportunity_score", 50)

        final = (
            (micro_score * 0.40) +
            (trader_score * 0.25) +
            (macro_score * 0.20) +
            (opportunity_score * 0.15)
        )

        if (
            micro.get("trend") == "bullish" and
            trader_score >= 70 and
            opportunity_score >= 70
        ):
            final += 8

        if micro.get("trend") == "bearish" and trader_score >= 65:
            final -= 10

        if opportunity_score < 40:
            final -= 5

        final = max(0, min(100, int(final)))

        return final


