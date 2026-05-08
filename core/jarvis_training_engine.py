"""
JARVIS 24/7 Training Engine — multi-asset AI learning brain.

Architecture:
  ┌──────────────────────────────────────────────────────────────────┐
  │  JarvisTrainingEngine (daemon thread, 5-minute cycles)          │
  │                                                                  │
  │  ┌─────────────┐  ┌───────────────┐  ┌────────────────────────┐ │
  │  │  Signal     │  │  Decision     │  │  Scoring & Learning    │ │
  │  │  Generator  │→ │  Recorder     │→ │  Loop                  │ │
  │  │  (yfinance) │  │  (SQLite)     │  │  (quality metrics)     │ │
  │  └─────────────┘  └───────────────┘  └────────────────────────┘ │
  │                                                                  │
  │  ┌─────────────┐  ┌───────────────┐  ┌────────────────────────┐ │
  │  │  Regime     │  │  Activity     │  │  Readiness             │ │
  │  │  Detector   │  │  Feed Writer  │  │  Engine                │ │
  │  └─────────────┘  └───────────────┘  └────────────────────────┘ │
  └──────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  MarketReplayEngine (on-demand, user-triggered)                 │
  │  Replays 8 pre-defined historical scenarios via yfinance        │
  └─────────────────────────────────────────────────────────────────┘

Safety: read-only market data only. No broker connections.
        real_trade: False always.
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.training")

# ── Symbol Universe ────────────────────────────────────────────────────────────

_EQUITY_POOL = [
    "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA", "AMD",
    "JPM", "BAC", "XOM", "JNJ", "V", "NFLX", "CRM", "PLTR",
]
_ETF_POOL   = ["SPY", "QQQ", "IWM", "TLT", "GLD", "USO", "XLF", "XLK"]
_CRYPTO_POOL = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"]
_FUTURES_PROXIES = {
    "ES (S&P)": "SPY", "NQ (Nasdaq)": "QQQ", "CL (Oil)": "USO",
    "GC (Gold)": "GLD", "ZN (10Y)": "TLT", "RTY (Russell)": "IWM",
}

_ASSET_CLASS_MAP: Dict[str, str] = {}
for s in _EQUITY_POOL:   _ASSET_CLASS_MAP[s] = "equity"
for s in _ETF_POOL:      _ASSET_CLASS_MAP[s] = "etf"
for s in _CRYPTO_POOL:   _ASSET_CLASS_MAP[s] = "crypto"
for v in _FUTURES_PROXIES.values(): _ASSET_CLASS_MAP[v] = "futures"

# All symbols deduplicated (proxies already in ETF pool)
_FULL_UNIVERSE = list(dict.fromkeys(
    _EQUITY_POOL + _ETF_POOL + _CRYPTO_POOL
))

# ── Strategy Styles ────────────────────────────────────────────────────────────

_STRATEGY_STYLES = [
    "momentum", "swing", "breakout", "mean_reversion",
    "trend_following", "volatility", "defensive",
]

# ── Training interval ──────────────────────────────────────────────────────────
_TRAIN_INTERVAL = int(os.getenv("JARVIS_TRAIN_INTERVAL", "300"))  # 5 min default
_SCORE_DELAY    = int(os.getenv("JARVIS_SCORE_DELAY",    "2"))    # cycles before scoring

# ── Historical replay scenarios ────────────────────────────────────────────────
REPLAY_SCENARIOS = {
    "2008_gfc":         {"name": "2008 Global Financial Crisis", "start": "2008-09-01", "end": "2009-03-01", "symbols": ["SPY","TLT","GLD"]},
    "covid_crash":      {"name": "COVID-19 Crash", "start": "2020-02-01", "end": "2020-05-01", "symbols": ["SPY","QQQ","AAPL"]},
    "fed_tightening":   {"name": "Fed Rate Tightening 2022", "start": "2022-01-01", "end": "2022-12-31", "symbols": ["SPY","TLT","QQQ"]},
    "ai_rally_2023":    {"name": "AI Bull Rally 2023", "start": "2023-01-01", "end": "2023-12-31", "symbols": ["QQQ","NVDA","MSFT"]},
    "meme_frenzy":      {"name": "Meme Stock Event 2021", "start": "2021-01-01", "end": "2021-03-31", "symbols": ["SPY","IWM","QQQ"]},
    "inflation_peak":   {"name": "Peak Inflation 2022-Q2", "start": "2022-04-01", "end": "2022-09-30", "symbols": ["SPY","TLT","GLD","USO"]},
    "crypto_bull_2021": {"name": "Crypto Bull Market 2021", "start": "2021-01-01", "end": "2021-11-30", "symbols": ["BTC-USD","ETH-USD"]},
    "crypto_winter":    {"name": "Crypto Winter 2022", "start": "2022-01-01", "end": "2022-12-31", "symbols": ["BTC-USD","ETH-USD"]},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Signal computation (pure computation, no side-effects) ─────────────────────

def _compute_signals(closes: List[float]) -> Optional[Dict]:
    """
    Compute momentum, RSI-proxy, MA cross, and volatility signals from close prices.
    Requires at least 25 prices.
    """
    if len(closes) < 25:
        return None
    try:
        # Momentum
        mom5  = (closes[-1] - closes[-6]) / closes[-6] * 100  if len(closes) >= 6  else 0
        mom20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 else 0

        # RSI-proxy via EMA of gains/losses (14-period)
        deltas  = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains   = [max(0, d) for d in deltas[-14:]]
        losses  = [max(0, -d) for d in deltas[-14:]]
        avg_g   = sum(gains) / 14
        avg_l   = sum(losses) / 14
        rsi     = 100 - (100 / (1 + avg_g / max(avg_l, 0.0001)))

        # SMA cross
        sma20  = sum(closes[-20:]) / 20
        sma50  = sum(closes[-min(50, len(closes)):]) / min(50, len(closes))
        price  = closes[-1]

        # Realized volatility (annualized %)
        rets   = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes[-20:]))]
        if len(rets) >= 2:
            mean_r = sum(rets) / len(rets)
            var_r  = sum((r - mean_r) ** 2 for r in rets) / len(rets)
            vol    = math.sqrt(var_r) * math.sqrt(252) * 100
        else:
            vol = 20.0

        return {
            "price":   round(price, 4),
            "rsi":     round(rsi, 1),
            "sma_cross": price > sma20 > sma50,
            "mom5":    round(mom5, 2),
            "mom20":   round(mom20, 2),
            "vol":     round(vol, 1),
        }
    except Exception:
        return None


def _make_decision(sig: Dict) -> Optional[Tuple[str, float, str]]:
    """
    Convert signals into (direction, confidence, strategy_style).
    Returns None if no clear signal.
    """
    bull = 0
    bear = 0

    # RSI oversold/overbought
    if sig["rsi"] < 32:  bull += 2
    elif sig["rsi"] < 42: bull += 1
    elif sig["rsi"] > 68: bear += 2
    elif sig["rsi"] > 58: bear += 1

    # SMA cross
    if sig["sma_cross"]:   bull += 2
    else:                  bear += 2

    # Momentum 5d
    if sig["mom5"] > 3:    bull += 2
    elif sig["mom5"] > 1:  bull += 1
    elif sig["mom5"] < -3: bear += 2
    elif sig["mom5"] < -1: bear += 1

    # Momentum 20d
    if sig["mom20"] > 8:   bull += 1
    elif sig["mom20"] < -8: bear += 1

    total = bull + bear
    if total == 0 or abs(bull - bear) < 2:
        return None  # no clear edge

    direction = "up" if bull > bear else "down"
    raw_score = max(bull, bear) / total
    confidence = round(min(0.88, max(0.35, raw_score * 0.75 + 0.2)), 3)

    # Determine strategy style from signal mix
    if sig["rsi"] < 35 or sig["rsi"] > 65:
        style = "mean_reversion"
    elif abs(sig["mom5"]) > 3 and sig["sma_cross"] == (direction == "up"):
        style = "momentum"
    elif sig["vol"] > 35:
        style = "volatility"
    elif abs(sig["mom20"]) > 8:
        style = "trend_following"
    else:
        style = "swing"

    return direction, confidence, style


def _apply_simulation_realism(price: float, side: str, vol: float) -> float:
    """Apply slippage + half-spread to simulate realistic fill."""
    slip_pct = 0.0005 + (vol / 100 * 0.0008)
    return round(price * (1 + slip_pct if side == "buy" else 1 - slip_pct), 4)


# ── Training Engine ────────────────────────────────────────────────────────────

class JarvisTrainingEngine:
    """
    24/7 multi-asset AI training engine.

    Separate from AutonomousPaperTrader — this engine focuses on:
    - Learning signal quality across 30+ symbols
    - Scoring decisions against actual price changes
    - Generating live activity feed
    - Maintaining regime detection
    - Running historical replay scenarios

    Does NOT execute paper trades (that's the autonomous trader's job).
    Calls to broker APIs: NONE. real_trade: False always.
    """

    def __init__(self) -> None:
        self._lock     = threading.Lock()
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._cycle    = 0
        self._last_run: Optional[str] = None
        self._errors:   List[str] = []
        self._current_regime = "sideways"
        self._scan_stats: Dict = {"symbols_scanned": 0, "decisions_made": 0, "scored": 0}

        # Pending decisions: id → {symbol, direction, price, cycle_decided}
        self._pending: Dict[int, Dict] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> Dict:
        if self._running:
            return {"status": "already_running", "real_trade": False}
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_loop, name="jarvis-training-engine", daemon=True
        )
        self._thread.start()
        self._post("JARVIS Training Engine started — 24/7 multi-asset learning active", "system")
        log.info("JarvisTrainingEngine started (interval=%ds)", _TRAIN_INTERVAL)
        return {"status": "started", "interval_secs": _TRAIN_INTERVAL, "real_trade": False}

    def stop(self) -> Dict:
        self._running = False
        self._post("Training Engine paused — learning suspended", "system", severity="warning")
        return {"status": "stopped", "real_trade": False}

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "running":        self._running,
                "cycle":          self._cycle,
                "last_run":       self._last_run,
                "current_regime": self._current_regime,
                "scan_stats":     dict(self._scan_stats),
                "pending_count":  len(self._pending),
                "recent_errors":  self._errors[-3:],
                "interval_secs":  _TRAIN_INTERVAL,
                "universe_size":  len(_FULL_UNIVERSE),
                "real_trade":     False,
            }

    def trigger_cycle(self) -> Dict:
        """Force an immediate training cycle (non-blocking)."""
        t = threading.Thread(target=self._training_cycle, name="jte-triggered", daemon=True)
        t.start()
        return {"status": "cycle_triggered", "real_trade": False}

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        while self._running:
            try:
                self._training_cycle()
            except Exception as exc:
                log.error("Training cycle error: %s", exc)
                with self._lock:
                    self._errors.append(f"{_now_iso()[:19]}: {str(exc)[:80]}")
            time.sleep(_TRAIN_INTERVAL)

    def _training_cycle(self) -> None:
        with self._lock:
            self._cycle += 1
            cycle = self._cycle
        self._last_run = _now_iso()
        log.debug("Training cycle #%d", cycle)

        # ── Step 1: Fetch market data ───────────────────────────────────────
        price_history = self._fetch_prices(_FULL_UNIVERSE)
        if not price_history:
            self._post("Market data temporarily unavailable — retrying next cycle", "system")
            return

        # ── Step 2: Detect regime ─────────────────────────────────────────
        regime = self._detect_regime(price_history)
        with self._lock:
            self._current_regime = regime

        # ── Step 3: Score pending decisions ───────────────────────────────
        self._score_pending(price_history)

        # ── Step 4: Generate new decisions ────────────────────────────────
        decisions_made = 0
        scanned = 0
        for sym, closes in price_history.items():
            scanned += 1
            sig = _compute_signals(closes)
            if not sig:
                continue
            result = _make_decision(sig)
            if not result:
                continue
            direction, confidence, style = result
            asset_class = _ASSET_CLASS_MAP.get(sym, "equity")

            # Apply realism
            fill_price = _apply_simulation_realism(sig["price"], "buy" if direction == "up" else "sell", sig["vol"])

            try:
                from opsx.memory.ai_memory_store import record_decision
                dec_id = record_decision(sym, asset_class, style, direction, confidence, fill_price)
                with self._lock:
                    self._pending[dec_id] = {
                        "symbol":    sym,
                        "direction": direction,
                        "price":     fill_price,
                        "cycle":     cycle,
                        "confidence": confidence,
                    }
                decisions_made += 1
            except Exception as exc:
                log.debug("record_decision failed: %s", exc)

            # Activity feed — selective, not every symbol
            if confidence >= 0.65 and decisions_made <= 6:
                self._post_signal(sym, asset_class, direction, confidence, style, sig)

        with self._lock:
            self._scan_stats["symbols_scanned"] += scanned
            self._scan_stats["decisions_made"]  += decisions_made

        # ── Step 5: Update learning memory ────────────────────────────────
        if cycle % 5 == 0:
            self._update_readiness()

        # ── Step 6: Crypto 24/7 note ──────────────────────────────────────
        crypto_found = [s for s in price_history if s in _CRYPTO_POOL]
        if crypto_found:
            self._post(
                f"24/7 crypto scan complete: {len(crypto_found)} assets — BTC/ETH/SOL active",
                "crypto"
            )

    # ── Price fetching ─────────────────────────────────────────────────────────

    def _fetch_prices(self, symbols: List[str]) -> Dict[str, List[float]]:
        """Batch-fetch 60 days of daily closes. Returns {symbol: [close, ...]}."""
        try:
            import yfinance as yf
            batch = " ".join(symbols)
            data  = yf.download(
                batch, period="3mo", interval="1d",
                group_by="ticker", auto_adjust=True, threads=True,
                progress=False,
            )
            result: Dict[str, List[float]] = {}
            if hasattr(data.columns, "levels"):
                # Multi-ticker result
                for sym in symbols:
                    try:
                        closes = data[sym]["Close"].dropna().tolist()
                        if len(closes) >= 25:
                            result[sym] = [float(c) for c in closes]
                    except Exception:
                        pass
            else:
                # Single-ticker result
                closes = data["Close"].dropna().tolist()
                if len(closes) >= 25 and symbols:
                    result[symbols[0]] = [float(c) for c in closes]
            return result
        except Exception as exc:
            log.warning("Price fetch failed: %s", exc)
            return {}

    # ── Regime detection ───────────────────────────────────────────────────────

    def _detect_regime(self, price_history: Dict[str, List[float]]) -> str:
        try:
            spy = price_history.get("SPY", [])
            vix_data: Optional[float] = None

            try:
                import yfinance as yf
                vf = yf.Ticker("^VIX").fast_info
                vix_data = float(getattr(vf, "last_price", None) or 0) or None
            except Exception:
                pass

            if len(spy) < 5:
                return "sideways"

            ret5  = (spy[-1] - spy[-5]) / spy[-5] * 100
            ret20 = (spy[-1] - spy[-min(20, len(spy))]) / spy[-min(20, len(spy))] * 100
            hi    = max(spy[-20:]) if len(spy) >= 20 else max(spy)
            lo    = min(spy[-20:]) if len(spy) >= 20 else min(spy)
            atr   = (hi - lo) / lo * 100

            if vix_data and vix_data >= 35: regime = "panic"
            elif vix_data and vix_data >= 25: regime = "high_vol"
            elif atr > 12:  regime = "high_vol"
            elif ret20 > 5 and ret5 > 0.5:  regime = "bull"
            elif ret20 < -5 and ret5 < -0.5: regime = "bear"
            elif abs(ret20) < 2: regime = "sideways"
            else: regime = "sideways"

            try:
                from opsx.memory.market_regime_memory import record_and_broadcast
                record_and_broadcast(regime, vix=vix_data, spy_ret_5d=ret5, spy_ret_20d=ret20)
            except Exception:
                pass

            # Activity feed for regime state
            regime_labels = {
                "bull":"Bullish","bear":"Defensive","high_vol":"High Volatility",
                "panic":"Risk-Off/Panic","sideways":"Neutral/Sideways",
            }
            vix_str = f" · VIX {vix_data:.1f}" if vix_data else ""
            self._post(
                f"Market regime: {regime_labels.get(regime, regime)}{vix_str} · SPY 5d {ret5:+.1f}% / 20d {ret20:+.1f}%",
                "regime"
            )
            return regime
        except Exception as exc:
            log.debug("Regime detection error: %s", exc)
            return "sideways"

    # ── Decision scoring ───────────────────────────────────────────────────────

    def _score_pending(self, price_history: Dict[str, List[float]]) -> None:
        """Score decisions from 1+ cycles ago against current prices."""
        with self._lock:
            to_score = {
                k: v for k, v in self._pending.items()
                if self._cycle - v["cycle"] >= _SCORE_DELAY
            }
        if not to_score:
            return

        try:
            from opsx.memory.ai_memory_store import score_decision, update_strategy_style, update_asset_perf
            from opsx.memory.strategy_rotation_memory import record_style_decision
            from opsx.memory.crypto_memory import record_crypto_decision
            from opsx.memory.futures_memory import record_futures_decision
        except Exception:
            return

        scored_count = 0
        for dec_id, dec in to_score.items():
            sym = dec["symbol"]
            closes = price_history.get(sym, [])
            if len(closes) < 2:
                continue

            entry_price = dec["price"]
            current     = closes[-1]
            pnl_pct     = (current - entry_price) / entry_price * 100

            predicted   = dec["direction"]
            actual      = "up" if pnl_pct >= 0 else "down"
            correct     = predicted == actual

            # Quality score: composite of direction accuracy + return magnitude
            dir_score   = 80 if correct else 20
            ret_score   = min(100, max(0, 50 + pnl_pct * 5))
            quality     = round(dir_score * 0.6 + ret_score * 0.4, 1)

            try:
                score_decision(dec_id, actual, round(pnl_pct, 3), quality)
            except Exception:
                pass

            asset = _ASSET_CLASS_MAP.get(sym, "equity")

            # Update memory modules
            style = "momentum"  # default; stored in DB but not retrieved here for perf
            try: record_style_decision(style, correct, quality)
            except Exception: pass

            try: update_asset_perf(asset, correct, quality)
            except Exception: pass

            if asset == "crypto":
                try: record_crypto_decision(sym, correct, quality)
                except Exception: pass

            if asset == "futures":
                try: record_futures_decision(sym, correct, quality)
                except Exception: pass

            # Activity feed for scored outcomes
            if abs(pnl_pct) >= 2:
                outcome = "correct" if correct else "incorrect"
                self._post(
                    f"Decision scored: {sym} {predicted.upper()} → {actual.upper()} "
                    f"({pnl_pct:+.1f}%) — {outcome.upper()} · quality {quality:.0f}/100",
                    "learning", symbol=sym, asset_class=asset,
                    confidence=dec.get("confidence"),
                    severity="info" if correct else "warning",
                )
            scored_count += 1

        # Remove scored from pending
        with self._lock:
            for k in to_score:
                self._pending.pop(k, None)
            self._scan_stats["scored"] += scored_count

    # ── Readiness update ───────────────────────────────────────────────────────

    def _update_readiness(self) -> None:
        try:
            from opsx.capital.jarvis_capital import jarvis_capital as _jc
            result = _jc.refresh_readiness()
            score  = result.get("score", 0)
            delta  = result.get("delta", 0)
            level  = result.get("level_name", "")
            if abs(delta) >= 1:
                direction = "improved" if delta > 0 else "declined"
                self._post(
                    f"AI Readiness {direction}: {score:.1f}% — {level}",
                    "readiness",
                    severity="info" if delta >= 0 else "warning",
                )
        except Exception as exc:
            log.debug("Readiness update failed: %s", exc)

    # ── Risk auto-adapt ────────────────────────────────────────────────────────

    def _auto_adapt_risk(self, regime: str, vix: Optional[float]) -> None:
        try:
            from opsx.memory.risk_adaptation_memory import auto_adapt
            from opsx.capital.capital_store import capital_store
            vault   = capital_store.get_vault()
            latest  = capital_store.get_latest_readiness()
            readiness = float(latest["score"]) if latest else 0
            new_mode = auto_adapt(regime, vix, readiness)
            if new_mode:
                current = vault.get("risk_mode", "balanced")
                from opsx.capital.jarvis_capital import jarvis_capital as _jc
                _jc.set_risk_mode(new_mode, trigger="auto_adapt")
                self._post(
                    f"Auto risk adaptation: {current} → {new_mode} "
                    f"(regime={regime}, VIX={vix:.1f if vix else '?'})",
                    "risk", severity="warning",
                )
        except Exception:
            pass

    # ── Activity feed helpers ──────────────────────────────────────────────────

    def _post(self, message: str, category: str = "general",
              symbol: Optional[str] = None, asset_class: Optional[str] = None,
              confidence: Optional[float] = None, severity: str = "info") -> None:
        try:
            from opsx.memory.ai_memory_store import post_activity
            post_activity(message, category=category, symbol=symbol,
                         asset_class=asset_class, confidence=confidence, severity=severity)
        except Exception:
            pass

    def _post_signal(self, sym: str, asset_class: str, direction: str,
                     confidence: float, style: str, sig: Dict) -> None:
        pct = confidence * 100
        rsi_note = f" · RSI {sig['rsi']:.0f}" if sig.get("rsi") else ""
        mom_note  = f" · mom {sig['mom5']:+.1f}%" if sig.get("mom5") else ""
        vol_note  = f" · vol {sig['vol']:.0f}%" if sig.get("vol", 0) > 35 else ""
        self._post(
            f"Analyzing {sym} [{style}]{rsi_note}{mom_note}{vol_note} "
            f"— {direction.upper()} signal · {pct:.0f}% confidence",
            category=asset_class, symbol=sym, asset_class=asset_class, confidence=confidence,
        )


# ── Historical Replay Engine ───────────────────────────────────────────────────

class MarketReplayEngine:
    """
    Replays historical scenarios through signal computation to test AI
    robustness across different market environments.

    Uses yfinance historical OHLCV data — no paid data required.
    """

    def run_replay(self, scenario_key: str) -> Dict:
        scenario = REPLAY_SCENARIOS.get(scenario_key)
        if not scenario:
            return {"status": "error", "error": f"Unknown scenario: {scenario_key}"}

        name    = scenario["name"]
        symbols = scenario["symbols"]
        start   = scenario["start"]
        end     = scenario["end"]

        try:
            from opsx.memory.ai_memory_store import post_activity
            post_activity(
                f"Market replay initiated: {name} ({start} → {end})",
                category="replay", severity="info",
            )
            results = self._simulate_scenario(symbols, start, end)
            self._persist_results(scenario_key, name, symbols, start, end, results)
            post_activity(
                f"Replay complete: {name} — win rate {results['win_rate']:.0f}%, "
                f"return {results['total_return']:+.1f}%, drawdown {results['max_drawdown']:.1f}%",
                category="replay", severity="info",
            )
            return {"status": "ok", "scenario": name, **results, "real_trade": False}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "real_trade": False}

    def _simulate_scenario(self, symbols: List[str], start: str, end: str) -> Dict:
        try:
            import yfinance as yf
        except ImportError:
            return {"win_rate": 0, "total_return": 0, "max_drawdown": 0, "decisions": 0}

        wins = 0
        total = 0
        returns: List[float] = []
        max_dd = 0.0

        for sym in symbols:
            try:
                hist = yf.Ticker(sym).history(start=start, end=end, interval="1d", auto_adjust=True)
                if hist.empty or len(hist) < 30:
                    continue
                closes = hist["Close"].tolist()

                # Simulate: make a decision every 5 days and score 5 days later
                for i in range(25, len(closes) - 5, 5):
                    window = closes[i-25:i]
                    sig    = _compute_signals(window)
                    if not sig:
                        continue
                    result = _make_decision(sig)
                    if not result:
                        continue
                    direction, conf, _ = result
                    entry = closes[i]
                    exit_ = closes[min(i+5, len(closes)-1)]
                    ret   = (exit_ - entry) / entry * 100
                    actual = "up" if ret >= 0 else "down"
                    correct = direction == actual
                    returns.append(ret if correct else -abs(ret))
                    total += 1
                    if correct:
                        wins += 1

            except Exception as exc:
                log.debug("Replay symbol %s error: %s", sym, exc)

        if not returns:
            return {"win_rate": 0, "total_return": 0, "max_drawdown": 0, "decisions": 0}

        total_return = sum(returns)
        peak = cum = 0.0
        for r in returns:
            cum += r
            peak = max(peak, cum)
            max_dd = max(max_dd, peak - cum)

        win_rate = wins / total * 100 if total else 0
        return {
            "win_rate":     round(win_rate, 1),
            "total_return": round(total_return, 2),
            "max_drawdown": round(-max_dd, 2),
            "decisions":    total,
            "lesson":       self._derive_lesson(win_rate, total_return, max_dd),
        }

    def _derive_lesson(self, win_rate: float, ret: float, dd: float) -> str:
        if win_rate >= 60 and ret > 10:
            return f"Strong performance in this regime — signals were well-calibrated."
        if dd > 20:
            return f"High drawdown detected — defensive mode would have reduced losses."
        if win_rate < 40:
            return f"Signals underperformed in this regime — reduce position size or skip."
        return f"Moderate performance — review exit timing and position sizing."

    def _persist_results(self, key: str, name: str, symbols: List[str],
                         start: str, end: str, results: Dict) -> None:
        try:
            from opsx.memory.ai_memory_store import save_replay_result
            save_replay_result(
                scenario=key, symbols=symbols, start=start, end=end,
                win_rate=results["win_rate"],
                total_return=results["total_return"],
                max_dd=abs(results["max_drawdown"]),
                decisions=results["decisions"],
                lessons=results.get("lesson", ""),
            )
        except Exception:
            pass


# ── Singletons ────────────────────────────────────────────────────────────────
training_engine = JarvisTrainingEngine()
replay_engine   = MarketReplayEngine()
