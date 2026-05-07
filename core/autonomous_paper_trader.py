"""
JARVIS Autonomous Paper Trader — institutional-grade continuous simulation.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │  AutonomousPaperTrader (daemon thread)                      │
  │    market regime detection (bull/bear/sideways/panic)       │
  │    symbol pool scanning (stocks + ETFs + crypto)            │
  │    adaptive confidence threshold (regime-based)             │
  │    strategy ranking via TraderLearningEngine                │
  │    reinforcement-style score adjustment                     │
  │    trade execution via PaperTradingEngine (simulated only)  │
  │    capital auto-refill below $5 000                         │
  │    persistent state to data/paper/autonomous/               │
  └─────────────────────────────────────────────────────────────┘

Safety invariants (enforced at multiple levels):
  - real_trade: False in every response
  - PaperTradingEngine blocks all real orders
  - No connection to any broker
  - No network calls to trading endpoints
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.autonomous_trader")

# ── Paths ─────────────────────────────────────────────────────────────────────
_STATE_PATH    = Path("data/paper/autonomous/state.json")
_LOG_PATH      = Path("data/paper/autonomous/trade_log.json")
_REGIME_PATH   = Path("data/paper/autonomous/regime.json")

# ── Symbol Pool ───────────────────────────────────────────────────────────────
_STOCK_POOL = [
    "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA", "AMD",
    "PLTR", "NFLX", "CRM", "ADBE", "ORCL", "JPM", "BAC", "GS",
    "XOM", "CVX", "JNJ", "UNH", "V", "MA",
]
_ETF_POOL = ["SPY", "QQQ", "IWM", "GLD", "TLT", "XLF", "XLK", "XLE"]
_CRYPTO_PROXY = ["COIN", "MSTR"]   # crypto-proxy stocks, not actual crypto

FULL_SYMBOL_POOL = _STOCK_POOL + _ETF_POOL + _CRYPTO_PROXY

# ── Regime thresholds ─────────────────────────────────────────────────────────
_REGIME_CONFIG = {
    "bull":        {"min_confidence": 58, "max_positions": 8,  "position_size_pct": 12},
    "sideways":    {"min_confidence": 63, "max_positions": 6,  "position_size_pct": 10},
    "bear":        {"min_confidence": 70, "max_positions": 4,  "position_size_pct": 7},
    "high_vol":    {"min_confidence": 72, "max_positions": 4,  "position_size_pct": 6},
    "panic":       {"min_confidence": 78, "max_positions": 2,  "position_size_pct": 5},
    "low_liquidity": {"min_confidence": 75, "max_positions": 3, "position_size_pct": 6},
}
_DEFAULT_REGIME = _REGIME_CONFIG["sideways"]

# ── Capital ───────────────────────────────────────────────────────────────────
_INITIAL_CAPITAL    = 100_000.0
_REFILL_THRESHOLD   = 5_000.0
_REFILL_TO          = 50_000.0

# ── Scan interval ─────────────────────────────────────────────────────────────
_SCAN_INTERVAL_SECS = int(os.getenv("AUTO_TRADER_INTERVAL", "900"))   # 15 min default


def _now() -> str:
    return datetime.utcnow().isoformat()


class AutonomousPaperTrader:
    """
    Daemon thread that continuously scans the symbol pool, detects market
    regime, filters candidates by confidence, and fires simulated trades
    via PaperTradingEngine.

    Start with .start(). Stop with .stop(). Status via .get_status().
    """

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._current_regime    = "sideways"
        self._last_scan_at:   Optional[str] = None
        self._last_trade_at:  Optional[str] = None
        self._trades_this_session = 0
        self._skipped_low_conf    = 0
        self._scan_count          = 0
        self._errors: List[str]   = []

        for p in [_STATE_PATH, _LOG_PATH, _REGIME_PATH]:
            p.parent.mkdir(parents=True, exist_ok=True)

        self._restore_state()

    # ── Public control ─────────────────────────────────────────────────────────

    def start(self) -> Dict:
        if self._running:
            return {"status": "already_running", "real_trade": False}
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_loop, name="autonomous-paper-trader", daemon=True
        )
        self._thread.start()
        log.info("AutonomousPaperTrader started (interval=%ss)", _SCAN_INTERVAL_SECS)
        return {"status": "started", "interval_secs": _SCAN_INTERVAL_SECS, "real_trade": False}

    def stop(self) -> Dict:
        self._running = False
        return {"status": "stopped", "real_trade": False}

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "running":              self._running,
                "current_regime":       self._current_regime,
                "regime_config":        _REGIME_CONFIG.get(self._current_regime, _DEFAULT_REGIME),
                "scan_count":           self._scan_count,
                "trades_this_session":  self._trades_this_session,
                "skipped_low_confidence": self._skipped_low_conf,
                "last_scan_at":         self._last_scan_at,
                "last_trade_at":        self._last_trade_at,
                "scan_interval_secs":   _SCAN_INTERVAL_SECS,
                "symbol_pool_size":     len(FULL_SYMBOL_POOL),
                "recent_errors":        self._errors[-5:],
                "real_trade":           False,
            }

    def trigger_scan(self) -> Dict:
        """Force an immediate scan cycle (non-blocking — runs in background thread)."""
        t = threading.Thread(target=self._scan_cycle, name="atp-triggered-scan", daemon=True)
        t.start()
        return {"status": "scan_triggered", "real_trade": False}

    # ── Internal loop ──────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        while self._running:
            try:
                self._scan_cycle()
            except Exception as exc:
                log.error("AutonomousPaperTrader scan error: %s", exc)
                with self._lock:
                    self._errors.append(f"{_now()}: {exc}")
            time.sleep(_SCAN_INTERVAL_SECS)

    def _scan_cycle(self) -> None:
        with self._lock:
            self._scan_count += 1
            self._last_scan_at = _now()

        regime = self._detect_regime()
        with self._lock:
            self._current_regime = regime
        cfg = _REGIME_CONFIG.get(regime, _DEFAULT_REGIME)

        log.info("APT scan #%d  regime=%s  min_conf=%d",
                 self._scan_count, regime, cfg["min_confidence"])

        try:
            from core.paper_trading_engine import PaperTradingEngine
            from core.trader_alpha_engine import TraderAlphaEngine
            from core.trader_learning_engine import TraderLearningEngine
        except ImportError as exc:
            log.warning("APT: required module unavailable — %s", exc)
            return

        engine   = PaperTradingEngine()
        alpha    = TraderAlphaEngine()
        learning = TraderLearningEngine()

        status = engine.get_status()
        cash   = float(status.get("cash", 0))

        # Capital auto-refill
        if cash < _REFILL_THRESHOLD:
            self._refill_capital(engine, _REFILL_TO - cash)
            cash = _REFILL_TO
            log.info("APT: capital refilled to $%.0f", cash)

        current_positions = len(engine.get_positions().get("positions", []))
        max_positions     = cfg["max_positions"]

        if current_positions >= max_positions:
            log.info("APT: at max positions (%d/%d), skip buys", current_positions, max_positions)
            self._check_exits(engine, alpha, learning)
            return

        slots_available = max_positions - current_positions
        candidates = self._rank_candidates(
            FULL_SYMBOL_POOL, alpha, learning, cfg["min_confidence"]
        )

        bought = 0
        for sym, score, action in candidates[:slots_available]:
            position_size = cash * (cfg["position_size_pct"] / 100.0)
            if position_size < 100:
                break

            # Get current price from alpha engine data
            price = self._get_price(alpha, sym)
            if not price or price <= 0:
                continue

            qty = max(1, int(position_size // price))
            result = engine.simulate_trade(sym, "buy", qty, price)
            if result.get("status") == "ok":
                bought  += 1
                log.info("APT: BUY %s x%d @ $%.2f  score=%.1f  regime=%s",
                         sym, qty, price, score, regime)
                self._log_trade({
                    "action": "buy", "symbol": sym, "qty": qty, "price": price,
                    "score": score, "regime": regime, "strategy": action,
                })
                with self._lock:
                    self._trades_this_session += 1
                    self._last_trade_at        = _now()
            else:
                log.debug("APT: simulate_trade rejected: %s", result.get("message"))

        # Exit check
        self._check_exits(engine, alpha, learning)
        self._save_state()
        self._save_regime(regime, cfg)

    def _detect_regime(self) -> str:
        """Derive market regime from SPY price action via yfinance."""
        try:
            import yfinance as yf
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1mo", interval="1d")
            if hist.empty or len(hist) < 5:
                return "sideways"

            closes    = hist["Close"].tolist()
            ret_20d   = (closes[-1] - closes[0]) / closes[0] * 100
            ret_5d    = (closes[-1] - closes[-5]) / closes[-5] * 100
            hi        = max(closes[-20:]) if len(closes) >= 20 else max(closes)
            lo        = min(closes[-20:]) if len(closes) >= 20 else min(closes)
            atr_pct   = (hi - lo) / lo * 100

            if atr_pct > 15:
                return "panic"
            if atr_pct > 8:
                return "high_vol"
            if ret_20d > 5 and ret_5d > 1:
                return "bull"
            if ret_20d < -5 and ret_5d < -1:
                return "bear"
            if abs(ret_20d) < 3:
                return "sideways"
            return "sideways"
        except Exception as exc:
            log.warning("APT regime detection failed: %s", exc)
            return "sideways"

    def _rank_candidates(
        self,
        symbols: List[str],
        alpha: Any,
        learning: Any,
        min_confidence: int,
    ) -> List[Tuple[str, float, str]]:
        """
        Scan symbols, filter by confidence threshold, rank by adjusted score.
        Returns list of (symbol, score, action) sorted by score descending.
        """
        ranked = []
        for sym in symbols:
            try:
                result = alpha._analyze_impl(sym)
                if "error" in result:
                    continue
                score  = float(result.get("score", 0))
                action = result.get("action", "NEUTRAL")

                # Only consider BUY signals above threshold
                if action not in ("BUY", "STRONG_BUY"):
                    continue
                if score < min_confidence:
                    with self._lock:
                        self._skipped_low_conf += 1
                    continue

                # Reinforcement-style adjustment from learning engine
                adj = learning.get_adapted_score_adjustment(sym, score)
                adjusted = float(adj.get("adjusted_score", score))

                ranked.append((sym, adjusted, action))
            except Exception:
                pass

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def _check_exits(self, engine: Any, alpha: Any, learning: Any) -> None:
        """Exit positions where signal has turned SELL or AVOID."""
        try:
            positions_data = engine.get_positions()
            positions      = positions_data.get("positions", [])
            for pos in positions:
                sym = pos.get("symbol", "")
                if not sym:
                    continue
                try:
                    result = alpha._analyze_impl(sym)
                    action = result.get("action", "NEUTRAL")
                    score  = float(result.get("score", 50))
                    if action in ("SELL", "STRONG_SELL", "AVOID") or score < 35:
                        qty   = int(pos.get("quantity", 0))
                        price = self._get_price(alpha, sym) or float(pos.get("avg_cost", 0))
                        if qty > 0 and price > 0:
                            r = engine.simulate_trade(sym, "sell", qty, price)
                            if r.get("status") == "ok":
                                log.info("APT: EXIT %s x%d @ $%.2f  action=%s",
                                         sym, qty, price, action)
                                self._log_trade({
                                    "action": "sell", "symbol": sym, "qty": qty,
                                    "price": price, "regime": self._current_regime,
                                    "reason": f"signal={action} score={score}",
                                })
                                with self._lock:
                                    self._trades_this_session += 1
                except Exception:
                    pass
        except Exception as exc:
            log.debug("APT _check_exits: %s", exc)

    def _get_price(self, alpha: Any, sym: str) -> Optional[float]:
        try:
            import yfinance as yf
            t = yf.Ticker(sym)
            info = t.fast_info
            price = float(getattr(info, "last_price", 0) or 0)
            if price > 0:
                return price
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        try:
            result = alpha._analyze_impl(sym)
            return float(result.get("price", 0) or 0)
        except Exception:
            return None

    def _refill_capital(self, engine: Any, amount: float) -> None:
        """Add virtual cash to the paper portfolio."""
        try:
            perf = engine._load_performance()
            perf["cash"] = perf.get("cash", 0) + amount
            perf["refill_count"] = perf.get("refill_count", 0) + 1
            perf["last_refill"]  = _now()
            engine._save_performance(perf)
        except Exception as exc:
            log.warning("APT refill failed: %s", exc)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _log_trade(self, entry: Dict) -> None:
        entry["timestamp"] = _now()
        entry["real_trade"] = False
        try:
            trades: List[Dict] = []
            if _LOG_PATH.exists():
                trades = json.loads(_LOG_PATH.read_text(encoding="utf-8"))
            trades.append(entry)
            _LOG_PATH.write_text(
                json.dumps(trades[-1000:], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("APT _log_trade: %s", exc)

    def _save_state(self) -> None:
        state = {
            "running":               self._running,
            "current_regime":        self._current_regime,
            "scan_count":            self._scan_count,
            "trades_this_session":   self._trades_this_session,
            "skipped_low_confidence": self._skipped_low_conf,
            "last_scan_at":          self._last_scan_at,
            "last_trade_at":         self._last_trade_at,
            "saved_at":              _now(),
            "real_trade":            False,
        }
        try:
            _STATE_PATH.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("APT _save_state: %s", exc)

    def _save_regime(self, regime: str, cfg: Dict) -> None:
        try:
            _REGIME_PATH.write_text(
                json.dumps({"regime": regime, "config": cfg, "detected_at": _now(),
                            "real_trade": False}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _restore_state(self) -> None:
        try:
            if _STATE_PATH.exists():
                state = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
                self._current_regime     = state.get("current_regime", "sideways")
                self._scan_count         = state.get("scan_count", 0)
                self._last_scan_at       = state.get("last_scan_at")
                self._last_trade_at      = state.get("last_trade_at")
                self._trades_this_session = 0   # reset on new process
        except Exception:
            pass

    def get_trade_log(self, limit: int = 50) -> Dict:
        try:
            if _LOG_PATH.exists():
                trades = json.loads(_LOG_PATH.read_text(encoding="utf-8"))
                return {"trades": trades[-limit:], "total": len(trades), "real_trade": False}
        except Exception:
            pass
        return {"trades": [], "total": 0, "real_trade": False}


# ── Module-level singleton ─────────────────────────────────────────────────────
autonomous_trader = AutonomousPaperTrader()
