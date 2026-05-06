"""
Trader Learning Engine — adaptive scoring and signal performance memory.

Tracks paper trade outcomes, recommendation accuracy, win rates,
confidence calibration, and portfolio-aware signal adaptation.

This is NOT autonomous ML training — it is rule-based adaptive scoring
backed by persistent JSON storage. The system progressively improves
recommendations over time by recalibrating confidence based on observed
outcomes.

Architecture:
  - Outcome records: each recommendation + paper trade → tracked outcome
  - Signal registry: per-signal win/loss/neutral rates
  - Confidence calibration: signal confidence vs actual accuracy
  - Volatility adaptation: track signal quality by market regime
  - Portfolio awareness: track which positions had the worst predictions
"""
from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.trader_learning")

_OUTCOMES_PATH   = Path("data/learning/signal_outcomes.json")
_METRICS_PATH    = Path("data/learning/learning_metrics.json")
_ACCURACY_PATH   = Path("data/learning/accuracy_history.json")
_CALIBRATION_PATH = Path("data/learning/confidence_calibration.json")

_MAX_OUTCOMES    = 2000
_MAX_ACCURACY    = 365


class TraderLearningEngine:
    """
    Adaptive scoring engine that learns from paper trade outcomes
    and historical recommendation accuracy.

    All weights are stored locally in JSON. No external ML dependencies.
    """

    # ── Record outcomes ───────────────────────────────────────────────────────

    def record_outcome(
        self,
        symbol: str,
        signal_type: str,          # "BUY" | "WATCH" | "AVOID" | "NEUTRAL"
        confidence: float,         # 0.0–1.0 from trader engine
        predicted_direction: str,  # "up" | "down" | "flat"
        actual_return_pct: float,  # observed return % over the tracking period
        holding_days: int,         # how long the position was held
        source: str = "paper",     # "paper" | "recommendation" | "audit"
        context: Optional[Dict] = None,
    ) -> Dict:
        """
        Record a trading outcome for learning.
        Classifies as win/loss/neutral and updates metrics.
        """
        outcome_label = self._classify_outcome(
            signal_type, predicted_direction, actual_return_pct
        )

        record = {
            "id":                  f"lo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{symbol}",
            "symbol":              symbol.upper(),
            "signal_type":         signal_type.upper(),
            "confidence":          round(confidence, 4),
            "predicted_direction": predicted_direction,
            "actual_return_pct":   round(actual_return_pct, 4),
            "holding_days":        holding_days,
            "outcome":             outcome_label,   # "win" | "loss" | "neutral"
            "source":              source,
            "context":             context or {},
            "recorded_at":         datetime.utcnow().isoformat(),
        }

        outcomes = self._load_outcomes()
        outcomes.append(record)
        if len(outcomes) > _MAX_OUTCOMES:
            outcomes = outcomes[-_MAX_OUTCOMES:]
        self._save_outcomes(outcomes)

        metrics = self._recompute_metrics(outcomes)
        self._save_metrics(metrics)

        return {
            "status":         "recorded",
            "outcome":        outcome_label,
            "record_id":      record["id"],
            "current_win_rate": metrics.get("overall_win_rate", 0),
            "real_trade":     False,
        }

    def record_paper_trade_outcome(
        self,
        paper_trade: Dict,
        current_price: float,
    ) -> Dict:
        """
        Helper to record outcome from a closed paper trade.
        Call when a position is closed (sell/trim to 0).
        """
        entry_price  = float(paper_trade.get("entry_price", paper_trade.get("avg_cost", 0)))
        if entry_price <= 0:
            return {"status": "skip", "reason": "no entry price"}

        actual_return = (current_price - entry_price) / entry_price * 100
        holding_days  = self._calc_holding_days(paper_trade.get("opened_at", ""))

        signal_type  = paper_trade.get("signal_at_entry", "BUY")
        confidence   = float(paper_trade.get("entry_confidence", 0.6))

        direction = "up" if actual_return > 0.5 else "down" if actual_return < -0.5 else "flat"

        return self.record_outcome(
            symbol=paper_trade.get("symbol", ""),
            signal_type=signal_type,
            confidence=confidence,
            predicted_direction="up" if signal_type == "BUY" else "down" if signal_type == "AVOID" else "flat",
            actual_return_pct=actual_return,
            holding_days=holding_days,
            source="paper",
            context={"trade_id": paper_trade.get("id", "")},
        )

    # ── Get metrics ───────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict:
        """
        Return the current learning metrics snapshot.
        Recomputes from outcomes if metrics file is stale.
        """
        metrics = self._load_metrics()
        outcomes = self._load_outcomes()

        if not metrics or len(outcomes) != metrics.get("_outcome_count", -1):
            metrics = self._recompute_metrics(outcomes)
            self._save_metrics(metrics)

        return {
            **metrics,
            "total_outcomes":    len(outcomes),
            "real_trade":        False,
            "last_updated":      datetime.utcnow().isoformat(),
        }

    def get_signal_performance(self) -> Dict:
        """Per-signal-type win rates and confidence calibration."""
        outcomes = self._load_outcomes()
        if not outcomes:
            return self._empty_signal_performance()

        by_signal: Dict[str, List[str]] = defaultdict(list)
        by_signal_conf: Dict[str, List[float]] = defaultdict(list)

        for o in outcomes:
            sig = o.get("signal_type", "UNKNOWN")
            by_signal[sig].append(o["outcome"])
            by_signal_conf[sig].append(o.get("confidence", 0.5))

        result = {}
        for sig, outcomes_list in by_signal.items():
            n     = len(outcomes_list)
            wins  = outcomes_list.count("win")
            losses = outcomes_list.count("loss")
            avg_conf = statistics.mean(by_signal_conf[sig]) if by_signal_conf[sig] else 0.5

            win_rate = wins / n if n > 0 else 0
            # Confidence calibration error: |confidence - win_rate|
            cal_error = abs(avg_conf - win_rate)

            result[sig] = {
                "signal_type":     sig,
                "total":           n,
                "wins":            wins,
                "losses":          losses,
                "neutrals":        n - wins - losses,
                "win_rate":        round(win_rate * 100, 1),
                "avg_confidence":  round(avg_conf * 100, 1),
                "calibration_error": round(cal_error * 100, 1),
                "calibrated":      cal_error < 0.15,
            }

        return {
            "status":           "ok",
            "by_signal":        result,
            "sample_size":      len(outcomes),
            "real_trade":       False,
        }

    def get_confidence_calibration(self) -> Dict:
        """
        Calibration curve: does high confidence → high accuracy?
        Buckets confidence [0,0.2), [0.2,0.4), ... [0.8,1.0]
        """
        outcomes = self._load_outcomes()
        if not outcomes:
            return {"status": "no_data", "buckets": [], "real_trade": False}

        buckets = [
            {"range": "0-20%",  "min": 0.0, "max": 0.2, "outcomes": []},
            {"range": "20-40%", "min": 0.2, "max": 0.4, "outcomes": []},
            {"range": "40-60%", "min": 0.4, "max": 0.6, "outcomes": []},
            {"range": "60-80%", "min": 0.6, "max": 0.8, "outcomes": []},
            {"range": "80-100%","min": 0.8, "max": 1.01,"outcomes": []},
        ]

        for o in outcomes:
            c = o.get("confidence", 0.5)
            for b in buckets:
                if b["min"] <= c < b["max"]:
                    b["outcomes"].append(o["outcome"])
                    break

        calibration = []
        for b in buckets:
            n = len(b["outcomes"])
            wins = b["outcomes"].count("win")
            calibration.append({
                "range":       b["range"],
                "count":       n,
                "win_rate":    round(wins / n * 100, 1) if n > 0 else 0,
                "expected_min": round(b["min"] * 100),
                "expected_max": round(b["max"] * 100),
            })

        return {
            "status":      "ok",
            "calibration": calibration,
            "real_trade":  False,
        }

    def get_recommendation_accuracy(self) -> Dict:
        """
        Accuracy of recommendations by symbol — which stocks
        was the trader right about most often?
        """
        outcomes = self._load_outcomes()
        if not outcomes:
            return {"status": "no_data", "by_symbol": [], "real_trade": False}

        by_sym: Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})
        for o in outcomes:
            sym = o.get("symbol", "?")
            by_sym[sym]["total"] += 1
            by_sym[sym]["wins"]  += (o["outcome"] == "win")
            by_sym[sym]["losses"] += (o["outcome"] == "loss")

        by_symbol = []
        for sym, d in sorted(by_sym.items(), key=lambda x: x[1]["total"], reverse=True):
            n  = d["total"]
            wr = round(d["wins"] / n * 100, 1) if n > 0 else 0
            by_symbol.append({
                "symbol":   sym,
                "total":    n,
                "wins":     d["wins"],
                "losses":   d["losses"],
                "win_rate": wr,
                "reliable": wr >= 55 and n >= 3,
            })

        return {
            "status":    "ok",
            "by_symbol": by_symbol[:20],
            "real_trade": False,
        }

    def get_adapted_score_adjustment(self, symbol: str, base_score: float) -> Dict:
        """
        Return a learning-based score adjustment for a symbol.
        If the system has tracked outcomes for this symbol, adjusts
        the confidence score up or down based on historical accuracy.

        Returns: {"adjusted_score": float, "adjustment": float, "confidence": str}
        """
        outcomes = self._load_outcomes()
        sym_outcomes = [o for o in outcomes if o.get("symbol") == symbol.upper()]

        if len(sym_outcomes) < 3:
            return {
                "adjusted_score": base_score,
                "adjustment":     0,
                "confidence":     "insufficient_data",
                "sample_size":    len(sym_outcomes),
            }

        wins   = sum(1 for o in sym_outcomes if o["outcome"] == "win")
        win_rate = wins / len(sym_outcomes)

        # Adjust base score by (historical win rate - 50%) * 20
        # i.e. 70% win rate adds +4 points, 30% win rate subtracts -4 points
        adjustment = round((win_rate - 0.5) * 20, 1)
        adjusted   = max(0, min(100, base_score + adjustment))

        return {
            "adjusted_score": round(adjusted, 1),
            "adjustment":     adjustment,
            "win_rate":       round(win_rate * 100, 1),
            "sample_size":    len(sym_outcomes),
            "confidence":     "high" if len(sym_outcomes) >= 10 else "medium" if len(sym_outcomes) >= 5 else "low",
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _classify_outcome(
        self,
        signal_type: str,
        predicted_direction: str,
        actual_return_pct: float,
    ) -> str:
        """
        Classify an outcome as win/loss/neutral.
        Win = signal direction matched actual movement by meaningful margin.
        """
        threshold = 1.0  # 1% move = meaningful

        if signal_type in ("BUY", "buy") or predicted_direction == "up":
            if actual_return_pct >= threshold:
                return "win"
            elif actual_return_pct <= -threshold:
                return "loss"
            return "neutral"

        elif signal_type in ("AVOID", "avoid") or predicted_direction == "down":
            if actual_return_pct <= -threshold:
                return "win"
            elif actual_return_pct >= threshold:
                return "loss"
            return "neutral"

        else:  # WATCH / NEUTRAL
            if abs(actual_return_pct) < threshold:
                return "win"
            return "neutral"

    def _recompute_metrics(self, outcomes: List[Dict]) -> Dict:
        """Recompute all aggregate metrics from raw outcomes."""
        if not outcomes:
            return self._empty_metrics()

        n      = len(outcomes)
        wins   = sum(1 for o in outcomes if o["outcome"] == "win")
        losses = sum(1 for o in outcomes if o["outcome"] == "loss")

        overall_win_rate = wins / n
        loss_rate        = losses / n

        # Recent trend (last 30)
        recent = outcomes[-30:]
        recent_wins = sum(1 for o in recent if o["outcome"] == "win")
        recent_win_rate = recent_wins / len(recent) if recent else overall_win_rate

        # Confidence calibration error
        confs = [o.get("confidence", 0.5) for o in outcomes]
        avg_confidence = statistics.mean(confs) if confs else 0.5
        cal_error = abs(avg_confidence - overall_win_rate)

        # Average holding days
        holding_days = [o.get("holding_days", 0) for o in outcomes if o.get("holding_days", 0) > 0]
        avg_holding = round(statistics.mean(holding_days), 1) if holding_days else 0

        # Return distribution
        returns = [o.get("actual_return_pct", 0) for o in outcomes]
        avg_return = round(statistics.mean(returns), 3) if returns else 0
        if len(returns) > 1:
            return_std = round(statistics.stdev(returns), 3)
            best_return  = round(max(returns), 2)
            worst_return = round(min(returns), 2)
        else:
            return_std = 0
            best_return = returns[0] if returns else 0
            worst_return = returns[0] if returns else 0

        # Signal breakdown
        by_signal: Dict[str, Dict] = defaultdict(lambda: {"wins": 0, "total": 0})
        for o in outcomes:
            sig = o.get("signal_type", "UNKNOWN")
            by_signal[sig]["total"] += 1
            by_signal[sig]["wins"]  += (o["outcome"] == "win")

        # Consecutive losses (drawdown signal)
        max_consec_losses = 0
        consec = 0
        for o in outcomes[-50:]:  # check last 50
            if o["outcome"] == "loss":
                consec += 1
                max_consec_losses = max(max_consec_losses, consec)
            else:
                consec = 0

        learning_quality = self._compute_learning_quality(
            overall_win_rate, cal_error, n, recent_win_rate
        )

        return {
            "total_outcomes":        n,
            "wins":                  wins,
            "losses":                losses,
            "neutrals":              n - wins - losses,
            "overall_win_rate":      round(overall_win_rate * 100, 1),
            "recent_win_rate_30":    round(recent_win_rate * 100, 1),
            "loss_rate":             round(loss_rate * 100, 1),
            "avg_confidence":        round(avg_confidence * 100, 1),
            "calibration_error":     round(cal_error * 100, 1),
            "is_overconfident":      avg_confidence > overall_win_rate + 0.10,
            "is_underconfident":     avg_confidence < overall_win_rate - 0.10,
            "avg_return_pct":        avg_return,
            "return_std":            return_std,
            "best_return_pct":       best_return,
            "worst_return_pct":      worst_return,
            "avg_holding_days":      avg_holding,
            "max_consecutive_losses": max_consec_losses,
            "signal_breakdown":      {
                sig: {
                    "win_rate": round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0,
                    "total":    d["total"],
                }
                for sig, d in by_signal.items()
            },
            "learning_quality_score": learning_quality,
            "learning_quality_label": self._quality_label(learning_quality),
            "_outcome_count":        n,
            "computed_at":           datetime.utcnow().isoformat(),
        }

    def _compute_learning_quality(
        self,
        win_rate: float,
        cal_error: float,
        n: int,
        recent_win_rate: float,
    ) -> int:
        """Score learning quality 0-100."""
        score = 40  # base

        # Sample size
        if n >= 50:    score += 15
        elif n >= 20:  score += 10
        elif n >= 10:  score += 5

        # Win rate
        if win_rate >= 0.6:  score += 20
        elif win_rate >= 0.5: score += 10
        elif win_rate < 0.35: score -= 10

        # Calibration
        if cal_error < 0.05:  score += 15
        elif cal_error < 0.15: score += 8
        elif cal_error > 0.30: score -= 10

        # Recent trend
        if recent_win_rate > win_rate + 0.1: score += 10  # improving
        elif recent_win_rate < win_rate - 0.1: score -= 5  # degrading

        return max(0, min(100, score))

    def _quality_label(self, score: int) -> str:
        if score >= 75: return "excellent"
        if score >= 55: return "good"
        if score >= 35: return "learning"
        return "insufficient_data"

    def _calc_holding_days(self, opened_at_iso: str) -> int:
        if not opened_at_iso:
            return 0
        try:
            opened = datetime.fromisoformat(opened_at_iso.replace("Z", "+00:00"))
            delta  = datetime.utcnow() - opened.replace(tzinfo=None)
            return max(0, delta.days)
        except Exception:
            return 0

    def _empty_metrics(self) -> Dict:
        return {
            "total_outcomes":         0,
            "wins":                   0,
            "losses":                 0,
            "neutrals":               0,
            "overall_win_rate":       0,
            "recent_win_rate_30":     0,
            "loss_rate":              0,
            "avg_confidence":         0,
            "calibration_error":      0,
            "is_overconfident":       False,
            "is_underconfident":      False,
            "avg_return_pct":         0,
            "return_std":             0,
            "best_return_pct":        0,
            "worst_return_pct":       0,
            "avg_holding_days":       0,
            "max_consecutive_losses": 0,
            "signal_breakdown":       {},
            "learning_quality_score": 0,
            "learning_quality_label": "insufficient_data",
            "_outcome_count":         0,
            "computed_at":            datetime.utcnow().isoformat(),
        }

    def _empty_signal_performance(self) -> Dict:
        return {
            "status":      "no_data",
            "by_signal":   {},
            "sample_size": 0,
            "real_trade":  False,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_outcomes(self) -> List[Dict]:
        try:
            if _OUTCOMES_PATH.exists():
                return json.loads(_OUTCOMES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save_outcomes(self, outcomes: List[Dict]) -> None:
        try:
            _OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
            _OUTCOMES_PATH.write_text(
                json.dumps(outcomes, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Outcomes save failed: %s", exc)

    def _load_metrics(self) -> Dict:
        try:
            if _METRICS_PATH.exists():
                return json.loads(_METRICS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_metrics(self, metrics: Dict) -> None:
        try:
            _METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _METRICS_PATH.write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # Append to accuracy history
            history: List[Dict] = []
            if _ACCURACY_PATH.exists():
                history = json.loads(_ACCURACY_PATH.read_text(encoding="utf-8"))
            history.append({
                "date":          datetime.utcnow().date().isoformat(),
                "win_rate":      metrics.get("overall_win_rate", 0),
                "total":         metrics.get("total_outcomes", 0),
                "quality_score": metrics.get("learning_quality_score", 0),
            })
            if len(history) > _MAX_ACCURACY:
                history = history[-_MAX_ACCURACY:]
            _ACCURACY_PATH.write_text(
                json.dumps(history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Metrics save failed: %s", exc)


# Singleton
trader_learning = TraderLearningEngine()
