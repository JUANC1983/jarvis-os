"""
Unified Multi-Broker Portfolio Engine.

Merges IBKR + Hapi into one intelligence layer while preserving broker separation.
All data is READ-ONLY. No trade execution. No order placement.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("jarvis.unified_portfolio")

_UNIFIED_PATH  = Path("data/portfolio/unified_snapshot.json")
_HISTORY_PATH  = Path("data/portfolio/portfolio_history.json")
_AUDIT_PATH    = Path("data/portfolio/portfolio_audit_log.json")


# ── Sector taxonomy ───────────────────────────────────────────────────────────

_SECTOR_MAP: Dict[str, str] = {
    "AAPL":   "Technology",  "MSFT":  "Technology",  "GOOGL": "Technology",
    "GOOG":   "Technology",  "META":  "Technology",  "NVDA":  "Technology",
    "AMD":    "Technology",  "INTC":  "Technology",  "CRM":   "Technology",
    "ADBE":   "Technology",  "ORCL":  "Technology",  "TSLA":  "Automotive",
    "AMZN":   "Consumer",    "SHOP":  "E-Commerce",  "BABA":  "Consumer",
    "JPM":    "Financials",  "BAC":   "Financials",  "GS":    "Financials",
    "MS":     "Financials",  "V":     "Financials",  "MA":    "Financials",
    "XOM":    "Energy",      "CVX":   "Energy",      "COP":   "Energy",
    "JNJ":    "Healthcare",  "UNH":   "Healthcare",  "PFE":   "Healthcare",
    "SPY":    "ETF",         "QQQ":   "ETF",         "VTI":   "ETF",
    "GLD":    "Commodities", "SLV":   "Commodities", "USO":   "Commodities",
    "BTC-USD":"Crypto",      "ETH-USD":"Crypto",     "PLTR":  "Technology",
    "NFLX":   "Media",       "DIS":   "Media",
}

_THEME_MAP: Dict[str, str] = {
    "NVDA": "AI/Semiconductor", "AMD": "AI/Semiconductor", "INTC": "AI/Semiconductor",
    "MSFT": "AI/Cloud",  "GOOGL": "AI/Cloud", "AMZN": "AI/Cloud", "CRM": "AI/Cloud",
    "PLTR": "AI/Defense", "META": "Social/AI",
    "BTC-USD": "Crypto", "ETH-USD": "Crypto",
    "GLD": "Safe Haven", "SLV": "Safe Haven",
    "XOM": "Energy Transition", "CVX": "Energy Transition",
    "TSLA": "EV/Clean Energy",
}


class UnifiedPortfolioEngine:
    """
    Aggregates portfolio data from multiple brokers into a single view.

    Usage:
        engine = UnifiedPortfolioEngine()
        snapshot = engine.build_snapshot(ibkr_data, hapi_data)
    """

    def build_snapshot(
        self,
        ibkr_data: Optional[Dict] = None,
        hapi_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Merge broker snapshots into a unified portfolio view.
        Both inputs are optional — missing brokers show as disconnected.
        """
        brokers: Dict[str, Dict] = {}
        all_positions: List[Dict] = []

        for broker_name, data in [("ibkr", ibkr_data), ("hapi", hapi_data)]:
            if not data:
                brokers[broker_name] = {
                    "status": "not_connected",
                    "positions": [],
                    "market_value": 0,
                    "cash": 0,
                    "daily_pnl": 0,
                    "unrealized_pnl": 0,
                    "position_count": 0,
                    "_stale": False,
                }
                continue

            positions = data.get("positions", [])
            pnl       = data.get("pnl", {})
            cash_data = data.get("cash", {})
            summary   = data.get("summary", {})

            broker_value = sum(p.get("market_value", 0) for p in positions)
            broker_cash  = float(
                cash_data.get("total_cash") or summary.get("total_cash") or 0
            )
            broker_daily    = float(pnl.get("daily_pnl") or summary.get("daily_pnl", 0) or 0)
            broker_unrealized = float(pnl.get("unrealized_pnl") or summary.get("unrealized_pnl", 0) or 0)

            brokers[broker_name] = {
                "status":          data.get("status", "unknown"),
                "account_id":      data.get("account_id", ""),
                "positions":       positions,
                "market_value":    round(broker_value, 2),
                "cash":            round(broker_cash, 2),
                "daily_pnl":       round(broker_daily, 2),
                "unrealized_pnl":  round(broker_unrealized, 2),
                "position_count":  len(positions),
                "fetched_at":      data.get("fetched_at", ""),
                "_stale":          data.get("_stale", False),
                "_stale_reason":   data.get("_stale_reason", ""),
            }
            all_positions.extend(positions)

        # ── Totals ────────────────────────────────────────────────────────────
        total_market_value = sum(b["market_value"] for b in brokers.values())
        total_cash         = sum(b["cash"] for b in brokers.values())
        total_daily_pnl    = sum(b["daily_pnl"] for b in brokers.values())
        total_unrealized   = sum(b["unrealized_pnl"] for b in brokers.values())
        total_portfolio    = total_market_value + total_cash

        # ── Weight calculation ────────────────────────────────────────────────
        for pos in all_positions:
            pos["weight_pct"] = (
                round(pos["market_value"] / total_market_value * 100, 2)
                if total_market_value > 0 else 0
            )
            # Enrich with sector/theme if missing
            sym = pos.get("symbol", "")
            if pos.get("sector", "unknown") == "unknown" and sym in _SECTOR_MAP:
                pos["sector"] = _SECTOR_MAP[sym]
            if not pos.get("theme") and sym in _THEME_MAP:
                pos["theme"] = _THEME_MAP[sym]

        # ── Sector exposure ───────────────────────────────────────────────────
        sector_exposure = self._calc_exposure(all_positions, "sector", total_market_value)
        theme_exposure  = self._calc_exposure(all_positions, "theme",  total_market_value)
        asset_exposure  = self._calc_exposure(all_positions, "asset_class", total_market_value)
        broker_exposure = [
            {"broker": name, "value": b["market_value"],
             "pct": round(b["market_value"] / total_market_value * 100, 1) if total_market_value else 0}
            for name, b in brokers.items()
        ]

        # ── Largest positions ─────────────────────────────────────────────────
        largest = sorted(all_positions, key=lambda p: p.get("market_value", 0), reverse=True)[:10]

        # ── Concentration warnings ────────────────────────────────────────────
        warnings = []
        for pos in all_positions:
            if pos.get("weight_pct", 0) > 20:
                warnings.append({
                    "type": "single_name_concentration",
                    "symbol": pos["symbol"],
                    "weight_pct": pos["weight_pct"],
                    "message": f"{pos['symbol']} = {pos['weight_pct']}% of portfolio — high single-name risk",
                })
        for sector_item in sector_exposure:
            if sector_item["pct"] > 35:
                warnings.append({
                    "type": "sector_concentration",
                    "sector": sector_item["label"],
                    "pct": sector_item["pct"],
                    "message": f"{sector_item['label']} sector = {sector_item['pct']}% of portfolio",
                })

        # ── Daily P&L percentage ──────────────────────────────────────────────
        daily_pnl_pct = (
            round(total_daily_pnl / (total_portfolio - total_daily_pnl) * 100, 2)
            if total_portfolio > total_daily_pnl > 0 or total_daily_pnl < 0
            else 0
        )

        snapshot = {
            "status":                  "ok",
            "total_market_value":      round(total_market_value, 2),
            "total_cash":              round(total_cash, 2),
            "total_portfolio_value":   round(total_portfolio, 2),
            "total_daily_pnl":         round(total_daily_pnl, 2),
            "total_daily_pnl_pct":     daily_pnl_pct,
            "total_unrealized_pnl":    round(total_unrealized, 2),
            "position_count":          len(all_positions),
            "brokers":                 brokers,
            "broker_exposure":         broker_exposure,
            "sector_exposure":         sector_exposure,
            "theme_exposure":          theme_exposure,
            "asset_class_exposure":    asset_exposure,
            "largest_positions":       largest,
            "concentration_warnings":  warnings,
            "all_positions":           all_positions,
            "generated_at":            datetime.utcnow().isoformat(),
            "real_trade":              False,
        }

        self._save_snapshot(snapshot)
        self._append_history(snapshot)
        return snapshot

    def get_cached_snapshot(self) -> Optional[Dict]:
        """Return the last saved snapshot or None."""
        try:
            if _UNIFIED_PATH.exists():
                data = json.loads(_UNIFIED_PATH.read_text(encoding="utf-8"))
                data["_from_cache"] = True
                return data
        except Exception:
            pass
        return None

    def empty_snapshot(self, reason: str = "no_data") -> Dict:
        return {
            "status":               "no_data",
            "reason":               reason,
            "total_market_value":   0,
            "total_cash":           0,
            "total_portfolio_value": 0,
            "total_daily_pnl":      0,
            "total_daily_pnl_pct":  0,
            "total_unrealized_pnl": 0,
            "position_count":       0,
            "brokers":              {},
            "broker_exposure":      [],
            "sector_exposure":      [],
            "theme_exposure":       [],
            "asset_class_exposure": [],
            "largest_positions":    [],
            "concentration_warnings": [],
            "all_positions":        [],
            "generated_at":         datetime.utcnow().isoformat(),
            "real_trade":           False,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _calc_exposure(
        self,
        positions: List[Dict],
        field: str,
        total_value: float,
    ) -> List[Dict]:
        buckets: Dict[str, float] = defaultdict(float)
        for pos in positions:
            label = pos.get(field, "unknown") or "unknown"
            buckets[label] += pos.get("market_value", 0)
        result = []
        for label, value in sorted(buckets.items(), key=lambda x: x[1], reverse=True):
            result.append({
                "label": label,
                "value": round(value, 2),
                "pct":   round(value / total_value * 100, 1) if total_value else 0,
            })
        return result

    def _save_snapshot(self, data: Dict) -> None:
        try:
            _UNIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
            _UNIFIED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Unified snapshot save failed: %s", exc)

    def _append_history(self, snapshot: Dict) -> None:
        try:
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            history: List[Dict] = []
            if _HISTORY_PATH.exists():
                history = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
            history.append({
                "timestamp":           snapshot["generated_at"],
                "total_market_value":  snapshot["total_market_value"],
                "total_cash":          snapshot["total_cash"],
                "total_daily_pnl":     snapshot["total_daily_pnl"],
                "total_unrealized_pnl": snapshot["total_unrealized_pnl"],
            })
            # Keep 365 daily snapshots
            if len(history) > 365:
                history = history[-365:]
            _HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Portfolio history append failed: %s", exc)


# Singleton
unified_portfolio = UnifiedPortfolioEngine()
