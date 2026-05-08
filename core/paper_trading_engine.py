"""
Paper Trading Engine — fully local simulation, no live orders.

CRITICAL SAFETY RULE:
  All responses include "real_trade": false.
  No external API calls to brokers.
  No order placement of any kind.
  This is a pure simulation engine backed by local JSON files
  AND a SQLite persistent store for durability across restarts.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger("jarvis.paper_trading")

try:
    from opsx.database.paperlab_store import store as _paperlab_store
    _STORE_AVAILABLE = True
except Exception as _store_err:
    _paperlab_store = None
    _STORE_AVAILABLE = False
    log.warning("PaperLab SQLite store unavailable: %s", _store_err)

_POSITIONS_PATH    = Path("data/portfolio/paper_positions.json")
_TRADES_PATH       = Path("data/portfolio/paper_trades.json")
_PERFORMANCE_PATH  = Path("data/portfolio/paper_performance.json")


def _now() -> str:
    return datetime.utcnow().isoformat()


class PaperTradingEngine:
    """
    Local paper trading simulation.

    Supports: import from real portfolio, buy/sell simulation, rebalance,
    performance tracking, paper vs real comparison.

    Every method returns "real_trade": false in the response.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        for p in [_POSITIONS_PATH, _TRADES_PATH, _PERFORMANCE_PATH]:
            p.parent.mkdir(parents=True, exist_ok=True)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        self.mark_to_market()
        positions = self._load_positions()
        trades    = self._load_trades()
        perf      = self._load_performance()
        total_value = sum(p.get("current_value", 0) for p in positions)
        cash = perf.get("cash", 100_000.0)
        return {
            "status":          "active",
            "position_count":  len(positions),
            "total_value":     round(total_value, 2),
            "cash":            round(cash, 2),
            "total_portfolio": round(total_value + cash, 2),
            "trade_count":     len(trades),
            "pnl_total":       round(perf.get("total_pnl", 0), 2),
            "pnl_pct":         round(perf.get("total_pnl_pct", 0), 2),
            "imported_from_real": perf.get("imported_from_real", False),
            "last_simulation_tick": perf.get("last_simulation_tick"),
            "data_origin":      "autonomous_sim",
            "real_trade":      False,
        }

    # ── Import from real portfolio ────────────────────────────────────────────

    def import_from_real(self, unified_snapshot: Dict) -> Dict:
        """
        Copy real portfolio positions into paper trading.
        Prices are taken at the time of import (mark-to-market at import).
        """
        all_positions = unified_snapshot.get("all_positions", [])
        if not all_positions:
            return {
                "status": "error",
                "message": "No positions in unified snapshot to import",
                "real_trade": False,
            }

        with self._lock:
            paper_positions = []
            for pos in all_positions:
                paper_positions.append({
                    "id":              f"pp_{uuid4().hex[:8]}",
                    "symbol":          pos.get("symbol", ""),
                    "name":            pos.get("name", ""),
                    "broker_source":   pos.get("broker", ""),
                    "asset_class":     pos.get("asset_class", "stock"),
                    "sector":          pos.get("sector", "unknown"),
                    "quantity":        pos.get("quantity", 0),
                    "import_price":    pos.get("market_price", 0),
                    "current_price":   pos.get("market_price", 0),
                    "current_value":   pos.get("market_value", 0),
                    "avg_cost":        pos.get("avg_cost", pos.get("market_price", 0)),
                    "unrealized_pnl":  0,
                    "unrealized_pnl_pct": 0,
                    "imported_at":     _now(),
                    "thesis":          "",
                    "paper_only":      False,
                })
            self._save_positions(paper_positions)

            total_value = sum(p["current_value"] for p in paper_positions)
            perf = self._load_performance()
            perf.update({
                "cash":                  unified_snapshot.get("total_cash", 100_000.0),
                "initial_value":         total_value,
                "imported_from_real":    True,
                "import_timestamp":      _now(),
                "total_pnl":             0,
                "total_pnl_pct":         0,
            })
            self._save_performance(perf)

        return {
            "status":          "ok",
            "imported":        len(paper_positions),
            "total_value":     round(total_value, 2),
            "real_trade":      False,
            "message":         f"Imported {len(paper_positions)} positions from real portfolio",
        }

    # ── Simulate trade ────────────────────────────────────────────────────────

    def simulate_trade(
        self,
        symbol: str,
        action: str,           # "buy" | "sell" | "trim" | "add"
        quantity: float,
        price: float,
        thesis: str = "",
    ) -> Dict:
        """
        Simulate a paper trade. Updates positions and records in trade log.
        """
        action = action.lower().strip()
        if action not in ("buy", "sell", "trim", "add"):
            return {"status": "error", "message": f"Invalid action '{action}'. Use: buy, sell, trim, add", "real_trade": False}
        if quantity <= 0 or price <= 0:
            return {"status": "error", "message": "quantity and price must be positive", "real_trade": False}

        _closed_trade_meta = None

        with self._lock:
            positions = self._load_positions()
            perf      = self._load_performance()
            cash      = float(perf.get("cash", 100_000.0))
            trade_value = round(quantity * price, 2)

            if action in ("buy", "add"):
                if cash < trade_value:
                    return {
                        "status": "error",
                        "message": f"Insufficient paper cash: ${cash:,.2f} available, ${trade_value:,.2f} needed",
                        "real_trade": False,
                    }
                # Update or create position
                existing = next((p for p in positions if p["symbol"] == symbol.upper()), None)
                if existing:
                    old_qty   = existing["quantity"]
                    new_qty   = old_qty + quantity
                    new_cost  = (existing["avg_cost"] * old_qty + price * quantity) / new_qty
                    existing["quantity"]     = round(new_qty, 6)
                    existing["avg_cost"]     = round(new_cost, 4)
                    existing["current_price"] = price
                    existing["current_value"] = round(new_qty * price, 2)
                    existing["unrealized_pnl"] = round((price - new_cost) * new_qty, 2)
                    existing["unrealized_pnl_pct"] = round((price - new_cost) / new_cost * 100, 2) if new_cost else 0
                    if thesis:
                        existing["thesis"] = thesis
                else:
                    positions.append({
                        "id":              f"pp_{uuid4().hex[:8]}",
                        "symbol":          symbol.upper(),
                        "name":            symbol.upper(),
                        "broker_source":   "paper",
                        "asset_class":     "stock",
                        "sector":          "unknown",
                        "quantity":        round(quantity, 6),
                        "import_price":    price,
                        "current_price":   price,
                        "current_value":   round(quantity * price, 2),
                        "avg_cost":        price,
                        "unrealized_pnl":  0,
                        "unrealized_pnl_pct": 0,
                        "imported_at":     _now(),
                        "thesis":          thesis,
                        "paper_only":      True,
                    })
                cash = round(cash - trade_value, 2)

            elif action in ("sell", "trim"):
                existing = next((p for p in positions if p["symbol"] == symbol.upper()), None)
                if not existing:
                    return {"status": "error", "message": f"No paper position in {symbol}", "real_trade": False}
                if existing["quantity"] < quantity:
                    return {
                        "status": "error",
                        "message": f"Only {existing['quantity']} shares available in paper position",
                        "real_trade": False,
                    }
                realized_pnl = round((price - existing["avg_cost"]) * quantity, 2)
                avg_cost = existing["avg_cost"]
                realized_pnl_pct = round((price - avg_cost) / avg_cost * 100, 2) if avg_cost else 0
                existing["quantity"] = round(existing["quantity"] - quantity, 6)
                existing["current_price"] = price
                if existing["quantity"] <= 0:
                    positions = [p for p in positions if p["symbol"] != symbol.upper()]
                else:
                    existing["current_value"] = round(existing["quantity"] * price, 2)
                    existing["unrealized_pnl"] = round((price - existing["avg_cost"]) * existing["quantity"], 2)
                    existing["unrealized_pnl_pct"] = round((price - existing["avg_cost"]) / existing["avg_cost"] * 100, 2) if existing["avg_cost"] else 0
                cash = round(cash + trade_value, 2)
                perf["total_pnl"] = round(perf.get("total_pnl", 0) + realized_pnl, 2)
                _closed_trade_meta = {
                    "symbol": symbol.upper(), "side": action,
                    "pnl": realized_pnl, "pnl_pct": realized_pnl_pct,
                    "strategy": thesis or "manual",
                }


            # Record trade
            trade_record = {
                "id":          f"pt_{uuid4().hex[:8]}",
                "symbol":      symbol.upper(),
                "action":      action,
                "quantity":    quantity,
                "price":       price,
                "value":       trade_value,
                "thesis":      thesis,
                "timestamp":   _now(),
                "real_trade":  False,
            }
            trades = self._load_trades()
            trades.append(trade_record)

            # Update performance
            perf["cash"] = cash
            initial = perf.get("initial_value", sum(p["current_value"] for p in positions) + cash)
            current_total = sum(p["current_value"] for p in positions) + cash
            perf["total_pnl_pct"] = round((current_total - initial) / initial * 100, 2) if initial else 0

            self._save_positions(positions)
            self._save_trades(trades)
            self._save_performance(perf)

        # Persist to SQLite store
        if _STORE_AVAILABLE:
            try:
                _paperlab_store.record_trade({
                    "id":          trade_record["id"],
                    "symbol":      trade_record["symbol"],
                    "side":        trade_record["action"],
                    "quantity":    trade_record["quantity"],
                    "entry_price": trade_record["price"],
                    "market_value": trade_record["value"],
                    "strategy":    thesis or "manual",
                    "ai_rationale": thesis,
                    "status":      "open" if action in ("buy", "add") else "closed",
                    "opened_at":   trade_record["timestamp"],
                    "real_trade":  False,
                })
            except Exception as _exc:
                log.debug("SQLite record_trade failed (non-fatal): %s", _exc)

        # Trigger AI learning evaluation for closed trades
        if action in ("sell", "trim") and _closed_trade_meta is not None:
            try:
                from opsx.memory.paperlab_memory import learning_memory as _lm
                _lm.evaluate_closed_trade({
                    "id":       trade_record["id"],
                    "symbol":   trade_record["symbol"],
                    "side":     action,
                    "pnl":      _closed_trade_meta["pnl"],
                    "pnl_pct":  _closed_trade_meta["pnl_pct"],
                    "strategy": thesis or "manual",
                    "confidence": 0.5,
                })
            except Exception as _exc:
                log.debug("Learning memory evaluation failed (non-fatal): %s", _exc)

        return {
            "status":      "ok",
            "trade":       trade_record,
            "cash_after":  cash,
            "real_trade":  False,
            "message":     f"Paper {action.upper()} {quantity} {symbol.upper()} @ ${price} = ${trade_value:,.2f}",
        }

    # ── Positions & performance ───────────────────────────────────────────────

    def get_positions(self) -> Dict:
        self.mark_to_market()
        positions   = self._load_positions()
        perf        = self._load_performance()
        cash        = perf.get("cash", 100_000.0)
        total_value = sum(p.get("current_value", 0) for p in positions)
        return {
            "status":      "ok",
            "positions":   positions,
            "cash":        round(cash, 2),
            "total_value": round(total_value, 2),
            "total_portfolio": round(total_value + cash, 2),
            "last_simulation_tick": perf.get("last_simulation_tick"),
            "data_origin": "autonomous_sim",
            "real_trade":  False,
        }

    def get_performance(self) -> Dict:
        self.mark_to_market()
        perf      = self._load_performance()
        positions = self._load_positions()
        trades    = self._load_trades()
        cash      = perf.get("cash", 100_000.0)
        total_value = sum(p.get("current_value", 0) for p in positions)
        initial     = perf.get("initial_value", total_value + cash)
        current     = total_value + cash
        total_pnl   = round(current - initial, 2)
        total_pnl_pct = round(total_pnl / initial * 100, 2) if initial else 0

        wins  = [t for t in trades if t.get("action") in ("sell", "trim") and t.get("value", 0) > 0]
        return {
            "status":            "ok",
            "initial_value":     round(initial, 2),
            "current_value":     round(current, 2),
            "total_pnl":         total_pnl,
            "total_pnl_pct":     total_pnl_pct,
            "cash":              round(cash, 2),
            "trade_count":       len(trades),
            "open_positions":    len(positions),
            "imported_from_real": perf.get("imported_from_real", False),
            "import_timestamp":  perf.get("import_timestamp", ""),
            "last_simulation_tick": perf.get("last_simulation_tick"),
            "data_origin":        "autonomous_sim",
            "real_trade":        False,
        }

    def mark_to_market(self) -> Dict:
        """Advance simulated prices/PnL without touching any broker."""
        with self._lock:
            positions = self._load_positions()
            if not positions:
                return {"status": "no_positions", "real_trade": False}
            bucket = int(time.time() // 60)
            total_unrealized = 0.0
            for pos in positions:
                sym = (pos.get("symbol") or "").upper()
                base = float(pos.get("current_price") or pos.get("avg_cost") or pos.get("import_price") or 1.0)
                avg = float(pos.get("avg_cost") or base)
                qty = float(pos.get("quantity") or 0)
                seed = sum(ord(c) for c in sym) + bucket
                pct_move = (((seed % 11) - 5) / 1000.0)
                price = round(max(0.01, base * (1 + pct_move)), 4)
                value = round(price * qty, 2)
                unrealized = round((price - avg) * qty, 2)
                pos["current_price"] = price
                pos["current_value"] = value
                pos["unrealized_pnl"] = unrealized
                pos["unrealized_pnl_pct"] = round((price - avg) / avg * 100, 2) if avg else 0
                pos["last_simulation_tick"] = _now()
                total_unrealized += unrealized
            perf = self._load_performance()
            cash = float(perf.get("cash", 100_000.0))
            current_total = sum(float(p.get("current_value", 0)) for p in positions) + cash
            initial = float(perf.get("initial_value", current_total) or current_total)
            perf["total_pnl"] = round(current_total - initial, 2)
            perf["total_pnl_pct"] = round((current_total - initial) / initial * 100, 2) if initial else 0
            perf["unrealized_pnl"] = round(total_unrealized, 2)
            perf["last_simulation_tick"] = _now()
            perf["data_origin"] = "autonomous_sim"
            self._save_positions(positions)
            self._save_performance(perf)

        # Persist snapshot to SQLite (every mark-to-market tick)
        if _STORE_AVAILABLE:
            try:
                _paperlab_store.save_snapshot({
                    "net_liquidation": round(current_total, 2),
                    "unrealized_pnl":  round(total_unrealized, 2),
                    "realized_pnl":    round(perf.get("total_pnl", 0) - total_unrealized, 2),
                    "cash":            round(cash, 2),
                    "buying_power":    round(cash, 2),
                    "position_count":  len(positions),
                    "positions":       [{"symbol": p.get("symbol"), "value": p.get("current_value", 0)} for p in positions],
                })
            except Exception as _exc:
                log.debug("SQLite save_snapshot failed (non-fatal): %s", _exc)

        return {"status": "ok", "positions": len(positions), "real_trade": False}

    def get_history(self) -> Dict:
        return {"status": "ok", "trades": self._load_trades(), "real_trade": False}

    def compare_with_real(self, unified_snapshot: Dict) -> Dict:
        """Compare paper portfolio composition vs real portfolio."""
        paper_positions = self._load_positions()
        real_positions  = unified_snapshot.get("all_positions", [])
        perf  = self._load_performance()
        cash  = perf.get("cash", 100_000.0)

        paper_total = sum(p["current_value"] for p in paper_positions) + cash
        real_total  = unified_snapshot.get("total_portfolio_value", 0)

        paper_symbols = {p["symbol"] for p in paper_positions}
        real_symbols  = {p["symbol"] for p in real_positions}

        in_paper_not_real = paper_symbols - real_symbols
        in_real_not_paper = real_symbols - paper_symbols
        in_both           = paper_symbols & real_symbols

        return {
            "status":              "ok",
            "paper_total":         round(paper_total, 2),
            "real_total":          round(real_total, 2),
            "difference":          round(paper_total - real_total, 2),
            "paper_position_count": len(paper_positions),
            "real_position_count": len(real_positions),
            "in_paper_not_real":   list(in_paper_not_real),
            "in_real_not_paper":   list(in_real_not_paper),
            "in_both":             list(in_both),
            "real_trade":          False,
        }

    def reset(self, initial_cash: float = 100_000.0) -> Dict:
        with self._lock:
            self._save_positions([])
            self._save_trades([])
            self._save_performance({
                "cash":               initial_cash,
                "initial_value":      initial_cash,
                "total_pnl":          0,
                "total_pnl_pct":      0,
                "imported_from_real": False,
            })
        return {"status": "ok", "message": f"Paper account reset with ${initial_cash:,.0f} cash", "real_trade": False}

    def rebalance(self, target_weights: Dict[str, float], current_prices: Dict[str, float]) -> Dict:
        """
        Simulate rebalancing to target weights.
        target_weights: {"AAPL": 20.0, "MSFT": 15.0, ...} (percentages)
        current_prices: {"AAPL": 185.0, ...}
        """
        positions = self._load_positions()
        perf      = self._load_performance()
        cash      = float(perf.get("cash", 0))
        total_value = sum(p.get("current_value", 0) for p in positions) + cash

        if sum(target_weights.values()) > 100.5:
            return {"status": "error", "message": "Target weights sum > 100%", "real_trade": False}

        trades_simulated = []
        for symbol, target_pct in target_weights.items():
            price = current_prices.get(symbol)
            if not price or price <= 0:
                continue
            target_value = total_value * target_pct / 100
            existing = next((p for p in positions if p["symbol"] == symbol), None)
            current_value = existing["current_value"] if existing else 0
            diff = target_value - current_value
            qty = abs(diff) / price
            if abs(diff) < 100:  # ignore tiny rebalance amounts
                continue
            action = "buy" if diff > 0 else "sell"
            trades_simulated.append({
                "symbol": symbol,
                "action": action,
                "quantity": round(qty, 4),
                "price": price,
                "value": round(qty * price, 2),
                "target_pct": target_pct,
                "current_pct": round(current_value / total_value * 100, 1) if total_value else 0,
            })

        return {
            "status":           "ok",
            "rebalance_trades": trades_simulated,
            "trade_count":      len(trades_simulated),
            "total_value":      round(total_value, 2),
            "real_trade":       False,
            "message":          f"Simulated {len(trades_simulated)} rebalance trades (not executed — use simulate_trade to apply)",
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_positions(self) -> List[Dict]:
        try:
            if _POSITIONS_PATH.exists():
                return json.loads(_POSITIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _load_trades(self) -> List[Dict]:
        try:
            if _TRADES_PATH.exists():
                return json.loads(_TRADES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _load_performance(self) -> Dict:
        try:
            if _PERFORMANCE_PATH.exists():
                return json.loads(_PERFORMANCE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"cash": 100_000.0, "initial_value": 100_000.0, "total_pnl": 0, "total_pnl_pct": 0}

    def _save_positions(self, data: List[Dict]) -> None:
        _POSITIONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_trades(self, data: List[Dict]) -> None:
        _TRADES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_performance(self, data: Dict) -> None:
        _PERFORMANCE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Singleton
paper_trading = PaperTradingEngine()
