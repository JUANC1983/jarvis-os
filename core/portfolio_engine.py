"""
Portfolio Engine — Phase 2.

Institutional-grade portfolio calculation layer.
Sits between broker connectors (ibkr_connector, hapi_readonly) and the
intelligence engine (portfolio_intelligence_engine).

Responsibilities:
  - Position-level metric enrichment (weight, cost basis, P&L %)
  - Portfolio-level aggregated statistics
  - Snapshot persistence with history
  - AI narrative summary generation
  - Risk scoring (0-100)

All outputs carry real_trade: False.
"""
from __future__ import annotations

import json
import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.portfolio_engine")

_SNAPSHOT_PATH  = Path("data/portfolio/portfolio_engine_snapshot.json")
_HISTORY_PATH   = Path("data/portfolio/portfolio_engine_history.json")
_MAX_HISTORY    = 365

# ── Benchmark constants ────────────────────────────────────────────────────────
_SAFE_CASH_MIN_PCT   = 5.0    # Below this: low liquidity risk
_SAFE_CASH_MAX_PCT   = 40.0   # Above this: excess cash drag
_CONCENTRATION_WARN  = 20.0   # Single position > this % → concentration risk
_SECTOR_WARN_PCT     = 35.0   # Single sector > this % → sector concentration
_LARGE_LOSS_PCT      = -10.0  # Unrealized loss worse than this → review needed
_LARGE_GAIN_PCT      = 15.0   # Unrealized gain above this → consider trimming


class PortfolioEngine:
    """
    Core portfolio calculation and snapshot engine.

    Usage:
        engine = PortfolioEngine()
        snapshot = engine.compute(unified_snapshot)  # from UnifiedPortfolioEngine
    """

    def compute(self, unified: Dict) -> Dict:
        """
        Compute enriched portfolio metrics from a unified broker snapshot.

        Input:  output from UnifiedPortfolioEngine.build_snapshot()
        Output: enriched snapshot with per-position metrics, aggregates, score
        """
        if not unified or unified.get("status") == "no_data":
            return self._empty_compute()

        positions     = unified.get("all_positions", [])
        total_value   = unified.get("total_market_value", 0.0)
        total_cash    = unified.get("total_cash", 0.0)
        daily_pnl     = unified.get("total_daily_pnl", 0.0)
        unrealized    = unified.get("total_unrealized_pnl", 0.0)
        sector_exp    = unified.get("sector_exposure", [])
        brokers       = unified.get("brokers", {})
        warnings      = unified.get("concentration_warnings", [])

        total_portfolio = total_value + total_cash

        # ── Position-level enrichment ─────────────────────────────────────────
        enriched = [self._enrich_position(p, total_value) for p in positions]

        # ── Aggregate metrics ─────────────────────────────────────────────────
        agg = self._aggregate(enriched, total_value, total_cash, daily_pnl, unrealized)

        # ── Performance tiers ─────────────────────────────────────────────────
        winners   = sorted(enriched, key=lambda p: p["unrealized_pnl"], reverse=True)[:5]
        losers    = sorted(enriched, key=lambda p: p["unrealized_pnl"])[:5]
        movers_up = sorted(enriched, key=lambda p: p["daily_pnl_pct"], reverse=True)[:5]
        movers_dn = sorted(enriched, key=lambda p: p["daily_pnl_pct"])[:5]

        # ── Risk score ────────────────────────────────────────────────────────
        score, risk_factors = self._score(
            enriched, total_value, total_cash, total_portfolio,
            daily_pnl, unrealized, sector_exp, warnings, brokers,
        )

        # ── AI narrative ──────────────────────────────────────────────────────
        narrative = self._narrative(agg, score, risk_factors, sector_exp, winners, losers)

        # ── Drawdown / volatility estimates ───────────────────────────────────
        drawdown_est = self._estimate_drawdown(enriched, total_value)

        snapshot = {
            "status":              "ok",
            "real_trade":          False,
            "computed_at":         datetime.utcnow().isoformat(),

            # Aggregates
            "total_market_value":  agg["total_market_value"],
            "total_cash":          agg["total_cash"],
            "total_portfolio":     agg["total_portfolio"],
            "total_daily_pnl":     agg["daily_pnl"],
            "total_daily_pnl_pct": agg["daily_pnl_pct"],
            "total_unrealized_pnl": agg["unrealized_pnl"],
            "total_unrealized_pct": agg["unrealized_pct"],
            "cost_basis":          agg["cost_basis"],
            "cash_pct":            agg["cash_pct"],
            "position_count":      len(enriched),

            # Enriched positions
            "positions":           enriched,

            # Performance breakdown
            "top_winners":         winners,
            "top_losers":          losers,
            "top_movers_up":       movers_up,
            "top_movers_down":     movers_dn,

            # Risk
            "portfolio_score":     score,
            "risk_level":          _score_to_level(score),
            "risk_factors":        risk_factors,
            "drawdown_estimate":   drawdown_est,

            # Narrative
            "ai_summary":          narrative,
            "ai_generated_at":     datetime.utcnow().isoformat(),
        }

        self._persist(snapshot)
        return snapshot

    # ── Position enrichment ───────────────────────────────────────────────────

    def _enrich_position(self, pos: Dict, total_value: float) -> Dict:
        """Add derived fields to a raw position dict."""
        qty        = float(pos.get("quantity", 0) or 0)
        avg_cost   = float(pos.get("avg_cost", 0) or 0)
        mkt_price  = float(pos.get("market_price", 0) or 0)
        mkt_value  = float(pos.get("market_value", 0) or 0)
        daily_pnl  = float(pos.get("daily_pnl", 0) or 0)

        cost_basis      = round(avg_cost * qty, 2)
        unrealized_pnl  = round(mkt_value - cost_basis, 2)
        unrealized_pct  = _safe_pct(unrealized_pnl, cost_basis)
        daily_pnl_pct   = float(pos.get("daily_pnl_pct", 0) or 0)
        if daily_pnl_pct == 0 and mkt_price > 0 and daily_pnl != 0:
            prev_price  = mkt_price - (daily_pnl / qty if qty else 0)
            daily_pnl_pct = _safe_pct(mkt_price - prev_price, prev_price)

        weight_pct = round(mkt_value / total_value * 100, 2) if total_value > 0 else 0.0

        return {
            **pos,
            "cost_basis":      cost_basis,
            "unrealized_pnl":  unrealized_pnl,
            "unrealized_pct":  unrealized_pct,
            "daily_pnl":       daily_pnl,
            "daily_pnl_pct":   daily_pnl_pct,
            "weight_pct":      weight_pct,
            "real_trade":      False,
        }

    # ── Aggregates ────────────────────────────────────────────────────────────

    def _aggregate(
        self,
        positions: List[Dict],
        total_value: float,
        total_cash: float,
        daily_pnl: float,
        unrealized: float,
    ) -> Dict:
        total_portfolio = total_value + total_cash
        cost_basis      = sum(p.get("cost_basis", 0) for p in positions)
        cash_pct        = _safe_pct(total_cash, total_portfolio)
        daily_pnl_pct   = _safe_pct(daily_pnl, total_portfolio - daily_pnl)
        unrealized_pct  = _safe_pct(unrealized, cost_basis) if cost_basis else 0.0

        return {
            "total_market_value": round(total_value, 2),
            "total_cash":         round(total_cash, 2),
            "total_portfolio":    round(total_portfolio, 2),
            "cost_basis":         round(cost_basis, 2),
            "daily_pnl":          round(daily_pnl, 2),
            "daily_pnl_pct":      round(daily_pnl_pct, 3),
            "unrealized_pnl":     round(unrealized, 2),
            "unrealized_pct":     round(unrealized_pct, 3),
            "cash_pct":           round(cash_pct, 2),
        }

    # ── Risk scoring ──────────────────────────────────────────────────────────

    def _score(
        self,
        positions: List[Dict],
        total_value: float,
        total_cash: float,
        total_portfolio: float,
        daily_pnl: float,
        unrealized: float,
        sector_exp: List[Dict],
        warnings: List[Dict],
        brokers: Dict,
    ) -> Tuple[int, List[Dict]]:
        """
        Score portfolio 0-100. Higher = lower risk / healthier portfolio.
        Returns (score, risk_factors[]).
        """
        score  = 55
        factors: List[Dict] = []

        def adj(delta: int, severity: str, message: str, category: str):
            nonlocal score
            score += delta
            factors.append({
                "category":  category,
                "severity":  severity,
                "message":   message,
                "delta":     delta,
            })

        n = len(positions)

        # Diversification
        if n == 0:
            adj(-35, "critical", "No hay posiciones activas", "diversification")
        elif n < 5:
            adj(-12, "high", f"Portafolio muy concentrado: {n} posiciones", "diversification")
        elif n < 10:
            adj(-5, "medium", f"Portafolio limitado: {n} posiciones", "diversification")
        elif n >= 15:
            adj(+5, "info", f"Buena diversificación: {n} posiciones", "diversification")

        # Concentration warnings
        for w in warnings:
            if w.get("type") == "single_name_concentration":
                pct = w.get("weight_pct", 0)
                if pct > 30:
                    adj(-10, "high", f"{w['symbol']} = {pct}% del portafolio", "concentration")
                else:
                    adj(-5, "medium", f"{w['symbol']} = {pct}% del portafolio", "concentration")

        # Sector concentration
        for w in warnings:
            if w.get("type") == "sector_concentration":
                adj(-6, "medium", f"Sector {w.get('sector')} = {w.get('pct')}%", "concentration")

        if sector_exp and len(sector_exp) >= 4:
            adj(+4, "info", f"Exposición en {len(sector_exp)} sectores", "diversification")

        # Cash ratio
        if total_portfolio > 0:
            cash_pct = total_cash / total_portfolio * 100
            if cash_pct < _SAFE_CASH_MIN_PCT:
                adj(-6, "medium", f"Efectivo muy bajo: {cash_pct:.1f}%", "liquidity")
            elif cash_pct > _SAFE_CASH_MAX_PCT:
                adj(+3, "info", f"Efectivo elevado: {cash_pct:.1f}% — liquidez buena", "liquidity")

        # Daily P&L
        if total_value > 0:
            dpct = daily_pnl / total_value * 100
            if dpct < -3:
                adj(-10, "high", f"Pérdida diaria severa: {dpct:.2f}%", "performance")
            elif dpct < -1.5:
                adj(-5, "medium", f"Pérdida diaria moderada: {dpct:.2f}%", "performance")
            elif dpct > 2:
                adj(+3, "info", f"Día positivo: +{dpct:.2f}%", "performance")

        # Unrealized P&L
        if total_value > 0:
            upct = unrealized / total_value * 100
            if upct < _LARGE_LOSS_PCT:
                adj(-10, "high", f"Pérdida no realizada: {upct:.1f}%", "performance")
            elif upct > _LARGE_GAIN_PCT:
                adj(+5, "info", f"Ganancia no realizada: +{upct:.1f}%", "performance")

        # Broker connectivity
        connected_brokers   = sum(1 for b in brokers.values() if b.get("status") not in ("not_connected", "disconnected", "not_configured"))
        stale_brokers       = sum(1 for b in brokers.values() if b.get("_stale"))
        if connected_brokers == 0:
            adj(-10, "high", "Ningún broker conectado — datos incompletos", "data_quality")
        if stale_brokers > 0:
            adj(-3, "medium", f"{stale_brokers} broker(s) con datos desactualizados", "data_quality")

        score = max(0, min(100, score))
        return score, factors

    # ── Drawdown estimate ─────────────────────────────────────────────────────

    def _estimate_drawdown(self, positions: List[Dict], total_value: float) -> Dict:
        """
        Estimate maximum drawdown potential based on unrealized losses.
        Uses position-level unrealized P&L as a proxy.
        """
        if not positions or total_value == 0:
            return {"max_loss_est": 0, "max_loss_pct": 0, "method": "no_data"}

        underwater = [p for p in positions if p.get("unrealized_pnl", 0) < 0]
        total_loss_est = sum(p.get("unrealized_pnl", 0) for p in underwater)
        max_loss_pct   = round(total_loss_est / total_value * 100, 2)

        return {
            "max_loss_est":     round(total_loss_est, 2),
            "max_loss_pct":     max_loss_pct,
            "underwater_count": len(underwater),
            "method":           "unrealized_pnl_proxy",
        }

    # ── AI narrative ─────────────────────────────────────────────────────────

    def _narrative(
        self,
        agg: Dict,
        score: int,
        risk_factors: List[Dict],
        sector_exp: List[Dict],
        winners: List[Dict],
        losers: List[Dict],
    ) -> str:
        """
        Generate a concise, institutional Spanish-language portfolio narrative.
        No external LLM calls — rule-based deterministic output.
        """
        lines: List[str] = []

        total_p  = agg["total_portfolio"]
        daily    = agg["daily_pnl"]
        unr      = agg["unrealized_pnl"]
        cash_pct = agg["cash_pct"]
        n        = agg.get("position_count", 0)
        level    = _score_to_level(score)

        # Opening
        daily_dir = "positivo" if daily >= 0 else "negativo"
        lines.append(
            f"Portafolio de ${total_p:,.0f} — {agg['position_count'] if 'position_count' in agg else '?'} posiciones activas. "
            f"P&L diario {daily_dir}: ${daily:+,.0f} ({agg['daily_pnl_pct']:+.2f}%). "
            f"P&L no realizado: ${unr:+,.0f} ({agg['unrealized_pct']:+.2f}%). "
            f"Score: {score}/100 ({level.upper()})."
        )

        # Cash commentary
        if cash_pct > _SAFE_CASH_MAX_PCT:
            lines.append(
                f"Efectivo elevado ({cash_pct:.1f}%) — considerar deployment gradual en activos de calidad."
            )
        elif cash_pct < _SAFE_CASH_MIN_PCT:
            lines.append(
                f"Efectivo crítico ({cash_pct:.1f}%) — capacidad de reacción muy limitada."
            )
        else:
            lines.append(f"Efectivo en rango saludable: {cash_pct:.1f}%.")

        # Sector commentary
        if sector_exp:
            top = sector_exp[0]
            lines.append(
                f"Mayor exposición sectorial: {top['label']} ({top['pct']}% del portafolio)."
            )
            if len(sector_exp) >= 4:
                lines.append(f"Diversificación en {len(sector_exp)} sectores — exposición balanceada.")

        # Top winner
        if winners and winners[0].get("unrealized_pnl", 0) > 0:
            w = winners[0]
            lines.append(
                f"Mejor posición: {w.get('symbol','?')} con P&L no realizado de ${w['unrealized_pnl']:+,.0f} ({w['unrealized_pct']:+.1f}%)."
            )

        # Top loser
        if losers and losers[0].get("unrealized_pnl", 0) < 0:
            l = losers[0]
            lines.append(
                f"Posición más débil: {l.get('symbol','?')} con P&L no realizado de ${l['unrealized_pnl']:+,.0f} ({l['unrealized_pct']:+.1f}%)."
            )

        # Risk flags
        high_risk = [f for f in risk_factors if f["severity"] in ("high", "critical")]
        if high_risk:
            flags = "; ".join(f["message"] for f in high_risk[:3])
            lines.append(f"Alertas activas: {flags}.")

        return " ".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self, snapshot: Dict) -> None:
        try:
            _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            _SNAPSHOT_PATH.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Portfolio engine snapshot save failed: %s", exc)

        try:
            history: List[Dict] = []
            if _HISTORY_PATH.exists():
                history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
            history.append({
                "timestamp":        snapshot["computed_at"],
                "total_portfolio":  snapshot["total_portfolio"],
                "total_cash":       snapshot["total_cash"],
                "daily_pnl":        snapshot["total_daily_pnl"],
                "unrealized_pnl":   snapshot["total_unrealized_pnl"],
                "portfolio_score":  snapshot["portfolio_score"],
                "position_count":   snapshot["position_count"],
            })
            if len(history) > _MAX_HISTORY:
                history = history[-_MAX_HISTORY:]
            _HISTORY_PATH.write_text(
                json.dumps(history, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Portfolio engine history append failed: %s", exc)

    def get_cached(self) -> Optional[Dict]:
        """Return last persisted snapshot."""
        try:
            if _SNAPSHOT_PATH.exists():
                d = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
                d["_from_cache"] = True
                return d
        except Exception:
            pass
        return None

    def get_history(self) -> List[Dict]:
        """Return historical portfolio snapshots (up to _MAX_HISTORY days)."""
        try:
            if _HISTORY_PATH.exists():
                return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _empty_compute(self) -> Dict:
        return {
            "status":              "no_data",
            "real_trade":          False,
            "computed_at":         datetime.utcnow().isoformat(),
            "total_market_value":  0,
            "total_cash":          0,
            "total_portfolio":     0,
            "total_daily_pnl":     0,
            "total_daily_pnl_pct": 0,
            "total_unrealized_pnl": 0,
            "total_unrealized_pct": 0,
            "cost_basis":          0,
            "cash_pct":            0,
            "position_count":      0,
            "positions":           [],
            "top_winners":         [],
            "top_losers":          [],
            "top_movers_up":       [],
            "top_movers_down":     [],
            "portfolio_score":     0,
            "risk_level":          "unknown",
            "risk_factors":        [],
            "drawdown_estimate":   {"max_loss_est": 0, "max_loss_pct": 0, "method": "no_data"},
            "ai_summary":          "Sin datos de portafolio. Conecta IBKR o Hapi para análisis en tiempo real.",
            "ai_generated_at":     datetime.utcnow().isoformat(),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator == 0 or math.isnan(denominator) or math.isinf(denominator):
        return 0.0
    return round(numerator / denominator * 100, 3)


def _score_to_level(score: int) -> str:
    if score >= 65:
        return "low"
    if score >= 45:
        return "medium"
    if score >= 25:
        return "high"
    return "critical"


# Singleton
portfolio_engine = PortfolioEngine()
