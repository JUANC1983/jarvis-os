"""
PaperLab Learning Memory — AI decision quality tracker.

Evaluates every closed paper trade against the original prediction,
scores decision quality, updates per-strategy confidence, and accumulates
structured lessons that feed back into future AI prompts.

Usage:
    from opsx.memory.paperlab_memory import learning_memory
    learning_memory.evaluate_closed_trade(trade_record, prediction)
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from opsx.database.paperlab_store import store as _store

log = logging.getLogger("jarvis.paperlab_memory")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Decision quality scoring ───────────────────────────────────────────────────

def _score_decision(
    predicted_direction: str,  # "up" | "down" | "neutral"
    actual_direction: str,      # "up" | "down" | "neutral"
    confidence: float,          # 0–1 from AI
    pnl: float,                 # realized P&L
    pnl_pct: float,             # P&L %
) -> Dict[str, Any]:
    """
    Score an AI trade decision on three axes:
      1. Direction accuracy (was the call right?)
      2. Confidence calibration (was confidence proportional to outcome?)
      3. P&L quality (how well did the trade perform relative to risk taken?)

    Returns a score dict with a 0–100 composite score.
    """
    # 1. Direction accuracy
    direction_correct = predicted_direction.lower() == actual_direction.lower()
    direction_score = 100 if direction_correct else 0

    # 2. Confidence calibration: penalize overconfidence on wrong calls,
    #    penalize underconfidence on right calls.
    if direction_correct:
        # Reward scaling with confidence — confident right call is best
        calibration_score = min(100, 50 + confidence * 50)
    else:
        # Overconfident wrong call is worst
        calibration_score = max(0, 50 - confidence * 50)

    # 3. P&L quality: normalize around ±5% as a reasonable range
    pnl_quality = min(100, max(0, 50 + pnl_pct * 10))

    # Composite: direction 50%, calibration 25%, P&L quality 25%
    composite = round(
        direction_score * 0.50 +
        calibration_score * 0.25 +
        pnl_quality * 0.25,
        1
    )

    grade = "A" if composite >= 80 else "B" if composite >= 65 else "C" if composite >= 50 else "D"

    return {
        "composite_score":    composite,
        "direction_score":    direction_score,
        "calibration_score":  round(calibration_score, 1),
        "pnl_quality_score":  round(pnl_quality, 1),
        "direction_correct":  direction_correct,
        "grade":              grade,
    }


def _derive_lesson(
    symbol: str,
    strategy: str,
    predicted_direction: str,
    actual_direction: str,
    pnl_pct: float,
    confidence: float,
    market_regime: Optional[str],
    score: Dict,
) -> str:
    """Generate a compact human-readable lesson string for this closed trade."""
    correct = score["direction_correct"]
    grade = score["grade"]
    regime_ctx = f" in {market_regime} regime" if market_regime else ""
    conf_str = f"{round(confidence * 100)}% confidence"

    if correct and pnl_pct > 2:
        return (
            f"{symbol} [{strategy}]{regime_ctx}: {conf_str} {predicted_direction} call correct"
            f", +{pnl_pct:.1f}% gain — grade {grade}. Reinforce signal."
        )
    elif correct and pnl_pct <= 0:
        return (
            f"{symbol} [{strategy}]{regime_ctx}: {conf_str} direction correct but exit too early"
            f", {pnl_pct:+.1f}% — grade {grade}. Review exit timing."
        )
    elif not correct and pnl_pct < -2:
        return (
            f"{symbol} [{strategy}]{regime_ctx}: {conf_str} {predicted_direction} wrong"
            f" (actual {actual_direction}), {pnl_pct:+.1f}% loss — grade {grade}. Reduce signal weight."
        )
    elif not correct and pnl_pct >= 0:
        return (
            f"{symbol} [{strategy}]{regime_ctx}: direction wrong but managed to exit positive"
            f", {pnl_pct:+.1f}% — grade {grade}. Luck element detected."
        )
    else:
        return (
            f"{symbol} [{strategy}]{regime_ctx}: {conf_str} {predicted_direction} → {actual_direction}"
            f", {pnl_pct:+.1f}% — grade {grade}."
        )


# ── Main learning memory class ──────────────────────────────────────────────

class PaperLabLearningMemory:
    """
    AI learning memory for PaperLab.

    Evaluates closed trades, scores decision quality, persists lessons to
    SQLite via PaperLabStore, and provides aggregated learning metrics.
    """

    # In-memory strategy confidence cache: strategy -> 0.0–1.0
    _confidence: Dict[str, float] = {}

    def evaluate_closed_trade(
        self,
        trade: Dict,
        prediction: Optional[Dict] = None,
    ) -> Dict:
        """
        Evaluate a closed trade and record the learning outcome.

        trade dict keys expected:
            id, symbol, strategy, side, entry_price, exit_price,
            pnl, pnl_pct, confidence, market_regime, ai_rationale

        prediction dict keys (optional, extracted from trade if absent):
            predicted_direction  ("up" | "down" | "neutral")
        """
        symbol    = trade.get("symbol", "")
        strategy  = trade.get("strategy") or "unknown"
        pnl       = float(trade.get("pnl", 0))
        pnl_pct   = float(trade.get("pnl_pct", 0))
        confidence = float(trade.get("confidence", 0.5))
        market_regime = trade.get("market_regime")

        # Derive predicted direction from trade side
        predicted_direction = "up"
        if prediction and prediction.get("predicted_direction"):
            predicted_direction = prediction["predicted_direction"]
        elif trade.get("side", "").lower() in ("sell", "short"):
            predicted_direction = "down"

        # Derive actual direction from P&L
        actual_direction = "up" if pnl >= 0 else "down"

        score = _score_decision(
            predicted_direction=predicted_direction,
            actual_direction=actual_direction,
            confidence=confidence,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

        lesson = _derive_lesson(
            symbol=symbol,
            strategy=strategy,
            predicted_direction=predicted_direction,
            actual_direction=actual_direction,
            pnl_pct=pnl_pct,
            confidence=confidence,
            market_regime=market_regime,
            score=score,
        )

        learning_record = {
            "trade_id":           trade.get("id", ""),
            "symbol":             symbol,
            "strategy":           strategy,
            "predicted_direction": predicted_direction,
            "actual_direction":   actual_direction,
            "predicted_correct":  score["direction_correct"],
            "confidence":         confidence,
            "pnl":                pnl,
            "market_regime":      market_regime,
            "lesson":             lesson,
        }

        try:
            _store.record_learning(learning_record)
            _store.update_strategy_stats(strategy, pnl)
        except Exception as exc:
            log.warning("Failed to persist learning record: %s", exc)

        # Update in-memory confidence for this strategy
        self._update_strategy_confidence(strategy, score["composite_score"])

        log.info(
            "Learning[%s] %s %s → %s | score=%.0f (%s) | pnl=%+.2f",
            trade.get("id", "?"), symbol, strategy,
            score["grade"], score["composite_score"],
            lesson[:60], pnl,
        )

        return {
            "symbol":           symbol,
            "strategy":         strategy,
            "score":            score,
            "lesson":           lesson,
            "strategy_confidence": self.get_strategy_confidence(strategy),
            "real_trade":       False,
        }

    def _update_strategy_confidence(self, strategy: str, composite_score: float) -> None:
        """
        Exponential moving average of composite scores per strategy.
        Converts composite (0–100) to a 0–1 confidence multiplier.
        """
        alpha = 0.2  # smoothing factor
        prev = self._confidence.get(strategy, 0.5)
        normalized = composite_score / 100.0
        self._confidence[strategy] = round(prev * (1 - alpha) + normalized * alpha, 4)

    def get_strategy_confidence(self, strategy: str) -> float:
        """Return current confidence multiplier for a strategy (0–1)."""
        return self._confidence.get(strategy, 0.5)

    def get_all_confidences(self) -> Dict[str, float]:
        return dict(self._confidence)

    def get_metrics(self) -> Dict:
        """Aggregated learning metrics for the dashboard."""
        try:
            summary = _store.get_learning_summary()
        except Exception:
            summary = {
                "total_decisions": 0, "correct": 0,
                "accuracy_pct": 0, "avg_confidence": 0,
                "recent_lessons": [],
            }

        total = summary.get("total_decisions", 0)
        correct = summary.get("correct", 0)
        accuracy = summary.get("accuracy_pct", 0)
        avg_conf = summary.get("avg_confidence", 0)

        # Learning quality score: penalizes overconfident wrong calls
        # Perfect would be: 100% accuracy with 100% confidence
        # Mediocre: 50% accuracy (random) regardless of confidence
        calibration_bonus = max(0, accuracy - 50) * 0.5 if total > 5 else 0
        base_score = accuracy
        learning_quality = min(100, round(base_score + calibration_bonus, 1))

        # Strategy confidence from in-memory EMA
        strategy_conf_summary = {
            k: round(v * 100, 1)
            for k, v in sorted(
                self._confidence.items(),
                key=lambda x: x[1], reverse=True
            )
        }

        return {
            "total_decisions":      total,
            "correct_predictions":  correct,
            "accuracy_pct":         accuracy,
            "avg_confidence_pct":   round(float(avg_conf) * 100, 1),
            "recent_lessons":       summary.get("recent_lessons", []),
            "learning_quality_score": learning_quality,
            "strategy_confidence":  strategy_conf_summary,
            "real_trade":           False,
        }

    def replay_history(self) -> int:
        """
        Rebuild in-memory strategy confidence from persisted learning records.
        Call once at startup to restore prior session confidence scores.
        """
        try:
            stats = _store.get_strategy_stats()
        except Exception:
            return 0
        count = 0
        for row in stats:
            strategy = row.get("strategy")
            win_rate = float(row.get("win_rate", 50))
            if strategy:
                # Convert historical win_rate to 0–1 confidence proxy
                self._confidence[strategy] = round(win_rate / 100.0, 4)
                count += 1
        log.info("PaperLab learning memory: replayed confidence for %d strategies", count)
        return count


# Module-level singleton — import this everywhere
learning_memory = PaperLabLearningMemory()

# Restore historical strategy confidence on module load
try:
    learning_memory.replay_history()
except Exception as _exc:
    log.warning("Learning memory replay failed: %s", _exc)
