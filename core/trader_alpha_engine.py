from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yfinance as yf


class TraderAlphaEngine:
    """
    Multi-factor technical analysis engine.
    Trend, momentum (RSI, MACD), volatility (ATR), and volume confirmation.
    Structured trade plan with entry zone, stop-loss, and R/R targets.
    """

    def run(self, symbol: str) -> Dict[str, Any]:
        return self.analyze(symbol)

    def analyze(self, symbol: str) -> Dict[str, Any]:
        clean = (symbol or "").strip().upper()
        if not clean:
            return {"error": "symbol required", "source": "trader_alpha"}

        try:
            ticker = yf.Ticker(clean)
            hist   = ticker.history(period="3mo", interval="1d")

            if hist.empty or len(hist) < 20:
                return {
                    "error":  f"Insufficient data for {clean} — try a liquid symbol",
                    "symbol": clean,
                    "source": "trader_alpha",
                }

            close  = hist["Close"]
            high   = hist["High"]
            low    = hist["Low"]
            volume = hist["Volume"] if "Volume" in hist.columns else None

            price = float(close.iloc[-1])

            # ── Indicators ──────────────────────────────────────────────
            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else ma20

            rsi          = self._rsi(close)
            macd, sig    = self._macd(close)
            atr          = self._atr(high, low, close)
            atr_pct      = round(atr / price * 100, 2)
            vol_ratio    = self._vol_ratio(volume)

            r20_high = float(high.iloc[-20:].max())
            r20_low  = float(low.iloc[-20:].min())

            # ── Scoring (base 50) ────────────────────────────────────────
            score   = 50
            signals: List[str] = []

            # Trend — MA alignment
            if price > ma20 > ma50:
                score += 18
                signals.append(f"Bullish trend: price {round(price,2)} > MA20 {round(ma20,2)} > MA50 {round(ma50,2)}")
            elif price < ma20 < ma50:
                score -= 18
                signals.append(f"Bearish trend: price {round(price,2)} < MA20 < MA50 — downtrend intact")
            elif price > ma50:
                score += 8
                signals.append(f"Neutral-bullish: above MA50 {round(ma50,2)} but below MA20")
            else:
                score -= 8
                signals.append(f"Below MA50 {round(ma50,2)} — structural weakness")

            # RSI
            rsi_v = round(rsi, 1)
            if 45 <= rsi < 65:
                score += 10
                signals.append(f"RSI {rsi_v}: healthy neutral range — room to run")
            elif rsi < 30:
                score += 8
                signals.append(f"RSI {rsi_v}: oversold — mean reversion watch")
            elif rsi >= 75:
                score -= 12
                signals.append(f"RSI {rsi_v}: overbought — elevated pullback risk")
            elif rsi < 45:
                score -= 5
                signals.append(f"RSI {rsi_v}: weak momentum")

            # MACD
            if macd > sig:
                score += 10
                signals.append("MACD bullish — momentum accelerating")
            else:
                score -= 5
                signals.append("MACD bearish — momentum decelerating")

            # Volume confirmation
            if vol_ratio is not None:
                if vol_ratio > 1.4:
                    score += 7
                    signals.append(f"Volume {round(vol_ratio,1)}× avg — strong institutional participation")
                elif vol_ratio < 0.7:
                    score -= 3
                    signals.append(f"Low volume {round(vol_ratio,1)}× avg — weak conviction")

            score = max(0, min(100, score))

            # ── Classification ───────────────────────────────────────────
            if score >= 78:
                action, light, conviction = "BUY",     "green",  "high"
            elif score >= 62:
                action, light, conviction = "WATCH",   "yellow", "medium"
            elif score <= 30:
                action, light, conviction = "AVOID",   "red",    "high"
            else:
                action, light, conviction = "NEUTRAL", "yellow", "low"

            # ── Trade plan ───────────────────────────────────────────────
            entry_low  = round(price * 0.990, 2)
            entry_high = round(price * 1.010, 2)
            stop_loss  = round(max(r20_low * 0.98, price * 0.92), 2)
            risk_per_share = round(price - stop_loss, 2)
            t1 = round(price + risk_per_share * 1.5, 2)
            t2 = round(price + risk_per_share * 2.5, 2)
            rr = round(risk_per_share * 1.5 / risk_per_share, 1) if risk_per_share > 0 else 0

            dist_res = round((r20_high - price) / price * 100, 1)
            dist_sup = round((price - r20_low) / price * 100, 1)

            return {
                "symbol":        clean,
                "price":         round(price, 2),
                "setup_score":   score,
                "traffic_light": light,
                "action":        action,
                "conviction":    conviction,
                "signals":       signals,

                "technicals": {
                    "price":         round(price, 2),
                    "ma20":          round(ma20, 2),
                    "ma50":          round(ma50, 2),
                    "rsi":           round(rsi, 1),
                    "atr_pct":       atr_pct,
                    "macd_bullish":  macd > sig,
                    "volume_ratio":  vol_ratio,
                },
                "levels": {
                    "support":                 round(r20_low, 2),
                    "resistance":              round(r20_high, 2),
                    "dist_to_resistance_pct":  dist_res,
                    "dist_to_support_pct":     dist_sup,
                },
                "trade_plan": {
                    "action":                action,
                    "entry_zone":            [entry_low, entry_high],
                    "stop_loss":             stop_loss,
                    "target_1":              t1,
                    "target_2":              t2,
                    "risk_reward_estimate":  f"{rr}:1",
                    "position_sizing_note":  f"Risk per trade: 1–2% of portfolio. ATR={atr_pct}% daily vol.",
                },
                "recommendations": {
                    "short_term": [
                        f"{action} at {round(price,2)} — {signals[0] if signals else 'mixed signals'}",
                        f"Entry zone {entry_low}–{entry_high}, hard stop {stop_loss} ({round((price-stop_loss)/price*100,1)}% risk)",
                        "Wait for price confirmation before entering — don't anticipate, react",
                    ],
                    "mid_term": [
                        f"Target 1: {t1} (+{round((t1-price)/price*100,1)}%), R/R {rr}:1",
                        f"Target 2: {t2} (+{round((t2-price)/price*100,1)}%) — trail stop after T1 hit",
                        "Reassess thesis at next earnings or major macro catalyst",
                    ],
                    "long_term": [
                        f"MA50 at {round(ma50,2)} is structural support — sustained break = exit thesis",
                        "Correlate position with existing holdings — avoid sector concentration",
                        "Annual fundamental review: is the business case still intact?",
                    ],
                },
                "risk_assessment": {
                    "level":          "medium",
                    "atr_volatility": f"{atr_pct}%/day",
                    "key_risk":       f"Stop {stop_loss} = {round((price-stop_loss)/price*100,1)}% drawdown — size to 1–2% portfolio risk max",
                    "resistance":     f"Next resistance at {round(r20_high,2)} ({dist_res}% away)",
                },
                "confidence":       round(score / 100, 2),
                "decision_clarity": conviction,
                "summary": (
                    f"{clean}: score {score}/100 — {action}. "
                    f"Price {round(price,2)}, RSI {round(rsi,1)}, "
                    f"R/R {rr}:1"
                ),
                "source":       "trader_alpha",
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            return {"error": str(exc), "symbol": clean, "source": "trader_alpha"}

    # ------------------------------------------------------------------
    # Technical indicators
    # ------------------------------------------------------------------

    def _rsi(self, close, period: int = 14) -> float:
        delta = close.diff()
        gain  = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss  = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs    = gain / loss.replace(0, float("nan"))
        rsi   = 100 - (100 / (1 + rs))
        val   = float(rsi.iloc[-1])
        return val if val == val else 50.0      # nan → neutral 50

    def _macd(
        self, close, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[float, float]:
        ema_f = close.ewm(span=fast, adjust=False).mean()
        ema_s = close.ewm(span=slow, adjust=False).mean()
        line  = ema_f - ema_s
        sig   = line.ewm(span=signal, adjust=False).mean()
        return float(line.iloc[-1]), float(sig.iloc[-1])

    def _atr(self, high, low, close, period: int = 14) -> float:
        h_l  = high - low
        h_pc = (high - close.shift(1)).abs()
        l_pc = (low  - close.shift(1)).abs()
        tr   = np.maximum(h_l, np.maximum(h_pc, l_pc))
        atr  = float(tr.rolling(period).mean().iloc[-1])
        return atr if atr == atr else float(high.iloc[-1] - low.iloc[-1])

    def _vol_ratio(self, volume) -> Optional[float]:
        if volume is None or len(volume) < 5:
            return None
        avg = float(volume.rolling(20).mean().iloc[-1])
        cur = float(volume.iloc[-1])
        if avg > 0:
            return round(cur / avg, 2)
        return None
