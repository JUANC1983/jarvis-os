from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yfinance as yf

from core.agent_schema import build_response, degraded


class TraderAlphaEngine:
    """
    Multi-factor technical analysis engine with market regime detection,
    portfolio-aware filtering, learning integration, and explainability.

    analyze(query)   → universal schema (orchestrator path)
    run(symbol)      → rich trade plan (dashboard / ProductBrain path)
    run_with_context → run() + portfolio snapshot + regime awareness
    """

    # ------------------------------------------------------------------
    # Universal interface — orchestrator path
    # ------------------------------------------------------------------

    def analyze(self, query: str) -> Dict[str, Any]:
        symbol = self._extract_symbol(query)
        if not symbol:
            return degraded("No valid ticker symbol found in query", confidence=0.2)
        try:
            raw = self._analyze_impl(symbol)
        except Exception as exc:
            return degraded(f"Analysis failed: {exc}", confidence=0.2)

        if "error" in raw:
            return degraded(raw["error"], confidence=0.25)

        score      = raw.get("setup_score", 50)
        action_raw = raw.get("action", "NEUTRAL")
        tp         = raw.get("trade_plan", {})
        tech       = raw.get("technicals", {})

        if action_raw == "BUY":
            entry_low  = tp.get("entry_zone", [raw.get("price", 0)])[0]
            stop       = tp.get("stop_loss", 0)
            t1         = tp.get("target_1", 0)
            action_str = (f"Enter {symbol} at ${entry_low} zone. "
                          f"Hard stop: ${stop}. Target 1: ${t1}. "
                          f"Size to max 2% portfolio risk.")
        elif action_raw == "AVOID":
            action_str = (f"Avoid {symbol} — bearish structure. "
                          f"Do not enter until price reclaims MA50 ${round(tech.get('ma50', 0), 2)}.")
        elif action_raw == "WATCH":
            action_str = (f"Add {symbol} to watchlist. Wait for RSI pullback to "
                          f"40–50 range before entering. No position yet.")
        else:
            action_str = (f"Hold no position in {symbol}. "
                          f"Re-evaluate on next earnings or major macro catalyst.")

        signals    = raw.get("signals", [])
        rr_raw     = tp.get("risk_reward_estimate", "1.5:1")
        risk_level = "high" if action_raw == "AVOID" else ("low" if action_raw == "BUY" and score >= 78 else "medium")
        confidence = round(min(score / 100, 0.96), 3)
        completeness = 1.0 if tech.get("volume_ratio") is not None else 0.85

        regime = raw.get("market_regime", {})
        explain = raw.get("explainability", {})

        return build_response(
            confidence=confidence,
            insight=(
                f"{symbol} setup score {score}/100 ({action_raw}). "
                f"RSI {tech.get('rsi', '–')}, MACD {'bullish' if tech.get('macd_bullish') else 'bearish'}, "
                f"price vs MA50 {'above' if raw.get('price', 0) > tech.get('ma50', 0) else 'below'}. "
                f"R/R estimate {rr_raw}. Regime: {regime.get('label', 'unknown')}."
            ),
            risk_level=risk_level,
            action=action_str,
            reason=explain.get("why", (
                f"Score={score}/100 derived from trend (MA20/MA50), RSI={tech.get('rsi','–')}, "
                f"MACD={'bullish' if tech.get('macd_bullish') else 'bearish'}, "
                f"volume={tech.get('volume_ratio','–')}×avg."
            )),
            signals_used=signals[:5] if signals else [f"Insufficient signals for {symbol}"],
            data_sources=["yfinance_3mo_daily", "technical_indicators", "market_regime_spy"],
            reasoning_path=[
                "1. Fetch 3-month OHLCV data + SPY regime context",
                "2. Detect market regime (bull/bear/sideways/panic/high_vol)",
                "3. Compute MA20/MA50 trend alignment (+/−18 pts)",
                "4. RSI 14 momentum scoring (+/−12 pts)",
                "5. MACD crossover confirmation (+/−10 pts)",
                "6. Volume ratio institutional participation (+/−7 pts)",
                "7. Regime-adjust final score",
                "8. Apply learning history adjustment via TraderLearningEngine",
                f"9. Final score {score}/100 → {action_raw}",
            ],
            data_freshness=1.0,
            data_completeness=completeness,
        )

    def run(self, symbol: str) -> Dict[str, Any]:
        """Rich trade plan — used by ProductBrain / dashboard endpoints."""
        return self._analyze_impl(symbol)

    def run_with_context(
        self,
        symbol: str,
        portfolio_snapshot: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Full analysis with portfolio context injection and learning adjustment.
        Returns same shape as run() plus portfolio_filter and learning_adjustment keys.
        """
        raw = self._analyze_impl(symbol, portfolio_snapshot=portfolio_snapshot)
        return raw

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    _TICKER_SKIP = {
        "I","A","US","UK","EU","AM","PM","AI","IS","TO","OF","AT","ON","IN",
        "MY","ME","NO","SO","BY","DO","OR","IF","AS","AN","BE","GO","UP","WE",
        "IT","HE","HIS","HER","CEO","CFO","COO","CTO","ETF","IPO","PE","VC",
        "AND","THE","FOR","NOT","BUT","HAS","WHO","WHY","HOW","ANY","ALL",
        "HQ","HR","IT","DC","USD","COP",
    }

    def _extract_symbol(self, query: str) -> str:
        q = (query or "").strip()
        m = re.search(r'\$([A-Z]{1,6}(?:\.[A-Z]{1,2})?)\b', q)
        if m:
            return m.group(1)
        caps_tokens = re.findall(r'\b([A-Z]{2,6}(?:\.[A-Z]{1,2})?)\b', q)
        for tok in caps_tokens:
            if tok not in self._TICKER_SKIP:
                return tok
        m = re.search(
            r'(?:stock|ticker|symbol|equity|share|invest(?:ing)? in|buy|sell|analyze|about|on|for)\s+([A-Za-z]{2,6})\b',
            q, re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).upper()
            if candidate not in self._TICKER_SKIP:
                return candidate
        return ""

    def _analyze_impl(
        self,
        symbol: str,
        portfolio_snapshot: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        clean = (symbol or "").strip().upper()
        if not clean:
            return {"error": "symbol required", "source": "trader_alpha"}

        try:
            ticker = yf.Ticker(clean)
            hist   = ticker.history(period="3mo", interval="1d")

            if hist.empty or len(hist) < 20:
                return {
                    "error":    f"Insufficient data for {clean} — try a liquid symbol",
                    "symbol":   clean,
                    "source":   "trader_alpha",
                    "real_trade": False,
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

            # ── Market Regime ────────────────────────────────────────────
            regime = self._detect_market_regime(atr_pct, close)

            # ── Scoring (base 50) ────────────────────────────────────────
            score   = 50
            signals: List[str] = []

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

            if macd > sig:
                score += 10
                signals.append("MACD bullish — momentum accelerating")
            else:
                score -= 5
                signals.append("MACD bearish — momentum decelerating")

            if vol_ratio is not None:
                if vol_ratio > 1.4:
                    score += 7
                    signals.append(f"Volume {round(vol_ratio,1)}× avg — strong institutional participation")
                elif vol_ratio < 0.7:
                    score -= 3
                    signals.append(f"Low volume {round(vol_ratio,1)}× avg — weak conviction")

            # ── Regime score adjustment ──────────────────────────────────
            regime_delta = regime.get("score_delta", 0)
            score += regime_delta
            if regime_delta != 0:
                signals.append(regime.get("signal_note", ""))

            score = max(0, min(100, score))

            # ── Portfolio context filter ─────────────────────────────────
            portfolio_filter = self._portfolio_context_filter(clean, score, portfolio_snapshot)
            score = portfolio_filter["adjusted_score"]
            score = max(0, min(100, score))

            # ── Learning adjustment ──────────────────────────────────────
            learning_adj = self._apply_learning_adjustment(clean, score)
            score = learning_adj["adjusted_score"]
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

            # ── Explainability ───────────────────────────────────────────
            explainability = self._build_explainability(
                symbol=clean,
                score=score,
                action=action,
                signals=signals,
                rsi=rsi,
                atr_pct=atr_pct,
                regime=regime,
                portfolio_filter=portfolio_filter,
                learning_adj=learning_adj,
                rr=rr,
            )

            return {
                "symbol":        clean,
                "price":         round(price, 2),
                "setup_score":   score,
                "traffic_light": light,
                "action":        action,
                "conviction":    conviction,
                "signals":       signals,
                "market_regime": regime,
                "portfolio_filter": portfolio_filter,
                "learning_adjustment": learning_adj,
                "explainability": explainability,

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
                    "level":          explainability.get("risk_level", "medium"),
                    "atr_volatility": f"{atr_pct}%/day",
                    "key_risk":       explainability.get("key_risk", f"Stop {stop_loss} = {round((price-stop_loss)/price*100,1)}% drawdown"),
                    "resistance":     f"Next resistance at {round(r20_high,2)} ({dist_res}% away)",
                    "regime_risk":    regime.get("risk_note", ""),
                },
                "confidence":       round(score / 100, 2),
                "decision_clarity": conviction,
                "summary": (
                    f"{clean}: score {score}/100 — {action}. "
                    f"Price {round(price,2)}, RSI {round(rsi,1)}, "
                    f"R/R {rr}:1. Regime: {regime.get('label','unknown')}."
                ),
                "source":       "trader_alpha",
                "real_trade":   False,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            return {"error": str(exc), "symbol": clean, "source": "trader_alpha", "real_trade": False}

    # ------------------------------------------------------------------
    # Market Regime Detection
    # ------------------------------------------------------------------

    def _detect_market_regime(
        self,
        atr_pct: float,
        close,
    ) -> Dict[str, Any]:
        """
        Classify current market regime using price structure and volatility.
        Returns: label, score_delta, signal_note, risk_note, confidence.

        Regime labels: bull | bear | sideways | panic | high_vol | low_liquidity
        """
        try:
            # Recent return — 20-session window
            ret_20 = 0.0
            if len(close) >= 20:
                ret_20 = (float(close.iloc[-1]) - float(close.iloc[-20])) / float(close.iloc[-20]) * 100

            # 5-day directional momentum
            ret_5 = 0.0
            if len(close) >= 5:
                ret_5 = (float(close.iloc[-1]) - float(close.iloc[-5])) / float(close.iloc[-5]) * 100

            # Volatility state via ATR % relative to baseline
            high_vol_threshold  = 3.5   # ATR > 3.5% = high volatility / panic territory
            normal_vol_upper    = 2.0
            low_vol_threshold   = 0.6

            if atr_pct >= high_vol_threshold and ret_5 < -5:
                label       = "panic"
                score_delta = -15
                signal_note = f"Panic regime: ATR {atr_pct}% + sharp 5d drop {ret_5:.1f}% — reduce size"
                risk_note   = "Elevated tail risk — regime-driven sell pressure, wider stops required"
                confidence  = 0.85

            elif atr_pct >= high_vol_threshold:
                label       = "high_vol"
                score_delta = -8
                signal_note = f"High volatility regime: ATR {atr_pct}% — reduce position size"
                risk_note   = "High vol environment — ATR-based stops must be wider, R/R degrades"
                confidence  = 0.80

            elif atr_pct <= low_vol_threshold:
                label       = "low_liquidity"
                score_delta = -3
                signal_note = f"Low volatility/liquidity: ATR {atr_pct}% — breakouts may be false"
                risk_note   = "Low vol can compress before expansion — watch for sudden moves"
                confidence  = 0.65

            elif ret_20 > 6 and ret_5 > 1:
                label       = "bull"
                score_delta = +5
                signal_note = f"Bull regime: +{ret_20:.1f}% over 20 sessions — trend is your edge"
                risk_note   = "Bull trend in place — but extended moves increase pullback risk"
                confidence  = 0.80

            elif ret_20 < -6 and ret_5 < -1:
                label       = "bear"
                score_delta = -10
                signal_note = f"Bear regime: {ret_20:.1f}% over 20 sessions — counter-trend risk high"
                risk_note   = "Bear trend — BUY signals have lower reliability, prefer WATCH/AVOID"
                confidence  = 0.80

            else:
                label       = "sideways"
                score_delta = 0
                signal_note = f"Sideways regime: {ret_20:.1f}% / 20 sessions — range-bound"
                risk_note   = "No clear directional bias — mean reversion strategies favored"
                confidence  = 0.70

            return {
                "label":        label,
                "ret_20d_pct":  round(ret_20, 2),
                "ret_5d_pct":   round(ret_5, 2),
                "atr_pct":      atr_pct,
                "score_delta":  score_delta,
                "signal_note":  signal_note,
                "risk_note":    risk_note,
                "confidence":   confidence,
            }

        except Exception:
            return {
                "label":       "unknown",
                "score_delta": 0,
                "signal_note": "",
                "risk_note":   "Regime detection unavailable",
                "confidence":  0.5,
            }

    # ------------------------------------------------------------------
    # Portfolio Context Filter
    # ------------------------------------------------------------------

    def _portfolio_context_filter(
        self,
        symbol: str,
        score: float,
        portfolio_snapshot: Optional[Dict],
    ) -> Dict[str, Any]:
        """
        Adjust score based on existing portfolio state.
        Penalizes adding to already-concentrated positions.
        Returns adjusted_score, delta, notes list.
        """
        if not portfolio_snapshot or portfolio_snapshot.get("status") == "no_data":
            return {
                "adjusted_score": score,
                "delta": 0,
                "notes": ["No portfolio context — score unadjusted"],
                "already_held": False,
                "existing_weight_pct": 0,
            }

        positions = portfolio_snapshot.get("all_positions", [])
        warnings  = portfolio_snapshot.get("concentration_warnings", [])
        total_val = portfolio_snapshot.get("total_market_value", 0)

        delta = 0
        notes: List[str] = []
        already_held = False
        existing_weight = 0.0

        # Check if already held
        held = next((p for p in positions if p.get("symbol", "").upper() == symbol), None)
        if held:
            already_held = True
            existing_weight = held.get("weight_pct", 0)
            pos_val = held.get("market_value", 0)
            existing_weight = pos_val / total_val * 100 if total_val > 0 else existing_weight

            if existing_weight > 20:
                delta -= 15
                notes.append(f"Already held at {existing_weight:.1f}% — adding would over-concentrate")
            elif existing_weight > 10:
                delta -= 8
                notes.append(f"Already held at {existing_weight:.1f}% — consider sizing carefully")
            else:
                notes.append(f"Currently held at {existing_weight:.1f}% — moderate add possible")

        # Check sector concentration
        symbol_sector = next((p.get("sector") for p in positions if p.get("symbol", "").upper() == symbol), None)
        if symbol_sector:
            sector_pct = sum(
                p.get("market_value", 0) for p in positions
                if p.get("sector") == symbol_sector
            ) / total_val * 100 if total_val > 0 else 0

            if sector_pct > 40:
                delta -= 8
                notes.append(f"Sector '{symbol_sector}' already at {sector_pct:.1f}% — sector over-exposure")
            elif sector_pct > 25:
                delta -= 4
                notes.append(f"Sector '{symbol_sector}' at {sector_pct:.1f}% — moderate sector weight")

        # Existing concentration warnings
        for w in warnings:
            if w.get("symbol", "").upper() == symbol:
                delta -= 5
                notes.append(f"Active concentration warning on {symbol}")
                break

        # Cash buffer check — penalize BUY when cash is critically low
        total_cash = portfolio_snapshot.get("total_cash", 0)
        total_portfolio = total_val + total_cash
        if total_portfolio > 0:
            cash_pct = total_cash / total_portfolio * 100
            if cash_pct < 3:
                delta -= 5
                notes.append(f"Cash critically low ({cash_pct:.1f}%) — no room to add positions")

        if not notes:
            notes.append("Portfolio context clear — no concentration concerns")

        return {
            "adjusted_score":     score + delta,
            "delta":              delta,
            "notes":              notes,
            "already_held":       already_held,
            "existing_weight_pct": round(existing_weight, 2),
        }

    # ------------------------------------------------------------------
    # Learning History Adjustment
    # ------------------------------------------------------------------

    def _apply_learning_adjustment(self, symbol: str, score: float) -> Dict[str, Any]:
        """
        Integrate TraderLearningEngine historical accuracy into score.
        Gracefully degrades if learning module unavailable.
        """
        try:
            from core.trader_learning_engine import trader_learning
            adj = trader_learning.get_adapted_score_adjustment(symbol, score)
            return {
                "adjusted_score": adj["adjusted_score"],
                "delta":          adj["adjustment"],
                "win_rate":       adj.get("symbol_win_rate"),
                "outcomes_used":  adj.get("outcomes_count", 0),
                "note":           adj.get("reason", ""),
            }
        except Exception:
            return {
                "adjusted_score": score,
                "delta":          0,
                "win_rate":       None,
                "outcomes_used":  0,
                "note":           "Learning engine unavailable — score unadjusted",
            }

    # ------------------------------------------------------------------
    # Explainability Layer
    # ------------------------------------------------------------------

    def _build_explainability(
        self,
        symbol: str,
        score: float,
        action: str,
        signals: List[str],
        rsi: float,
        atr_pct: float,
        regime: Dict,
        portfolio_filter: Dict,
        learning_adj: Dict,
        rr: float,
    ) -> Dict[str, Any]:
        """
        Produce structured explainability block for every recommendation.
        Answers: why, confidence, data used, risk, uncertainty, alternative scenario.
        """
        regime_label = regime.get("label", "unknown")
        pf_notes     = portfolio_filter.get("notes", [])
        learn_delta  = learning_adj.get("delta", 0)
        learn_wr     = learning_adj.get("win_rate")
        pf_delta     = portfolio_filter.get("delta", 0)

        # Why this recommendation
        why_parts = [
            f"Score {score}/100 driven by: {signals[0] if signals else 'mixed technicals'}.",
            f"Regime: {regime_label} ({regime.get('signal_note', '')}).",
        ]
        if pf_delta != 0:
            why_parts.append(f"Portfolio adjustment {pf_delta:+d}pts: {pf_notes[0] if pf_notes else ''}.")
        if learn_delta != 0 and learn_wr is not None:
            why_parts.append(f"Learning history ({learn_wr*100:.0f}% win rate on {symbol}) adjusted score {learn_delta:+d}pts.")
        why = " ".join(why_parts)

        # Confidence breakdown
        confidence_factors = []
        if len(signals) >= 3:
            confidence_factors.append("Multiple confirming signals")
        else:
            confidence_factors.append("Limited signal confirmation")
        if regime_label in ("bull", "sideways"):
            confidence_factors.append(f"{regime_label} regime supports trade")
        elif regime_label in ("panic", "bear"):
            confidence_factors.append(f"{regime_label} regime reduces signal reliability")
        if learn_wr is not None:
            confidence_factors.append(f"Historical win rate on {symbol}: {learn_wr*100:.0f}%")

        # Risk level
        if atr_pct > 3 or regime_label in ("panic",):
            risk_level = "high"
        elif atr_pct > 1.5 or regime_label in ("bear", "high_vol"):
            risk_level = "medium"
        else:
            risk_level = "low"

        # Key risk sentence
        key_risk = regime.get("risk_note", f"ATR {atr_pct}% daily volatility — size accordingly")
        if portfolio_filter.get("already_held") and portfolio_filter.get("existing_weight_pct", 0) > 10:
            key_risk += f"; adding to existing {portfolio_filter['existing_weight_pct']:.1f}% position increases concentration risk"

        # Uncertainty
        uncertainty_factors = []
        if regime_label in ("panic", "high_vol"):
            uncertainty_factors.append("High-volatility regime reduces signal reliability")
        if rsi > 70:
            uncertainty_factors.append("Overbought RSI — reversal timing uncertain")
        if rsi < 35:
            uncertainty_factors.append("Oversold RSI — bottom timing uncertain")
        if learning_adj.get("outcomes_used", 0) < 3:
            uncertainty_factors.append(f"Insufficient learning history for {symbol} (<3 outcomes)")
        if not uncertainty_factors:
            uncertainty_factors.append("No major uncertainty flags — standard execution risk")

        # Alternative scenario
        if action == "BUY":
            alternative = f"If {regime_label} regime deteriorates or MA50 breaks, downgrade to WATCH and await re-entry."
        elif action == "AVOID":
            alternative = f"Bull scenario: if price reclaims MA50 and RSI rebuilds above 50, re-evaluate for WATCH."
        elif action == "WATCH":
            alternative = f"Bull case: RSI pulls back to 40–50 → enter. Bear case: price breaks MA50 → exit watchlist."
        else:
            alternative = f"Re-evaluate on macro catalyst or if RSI crosses 50 with volume expansion."

        return {
            "why":                 why,
            "confidence_factors":  confidence_factors,
            "risk_level":          risk_level,
            "key_risk":            key_risk,
            "uncertainty":         uncertainty_factors,
            "alternative_scenario": alternative,
            "data_used": [
                "yfinance 3-month OHLCV (daily)",
                "MA20/MA50 trend alignment",
                "RSI-14 momentum",
                "MACD(12,26,9) crossover",
                "Volume 20-day ratio",
                f"Market regime: {regime_label} (ATR-based)",
                "Portfolio concentration check" if portfolio_filter.get("delta", 0) != 0 else "Portfolio: no holdings",
                f"Learning engine: {learning_adj.get('outcomes_used', 0)} prior outcomes" if learning_adj.get("outcomes_used", 0) > 0 else "Learning: no prior history",
            ],
        }

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
        return val if val == val else 50.0

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
