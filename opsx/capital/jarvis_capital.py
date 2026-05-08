"""
JARVIS Capital OS — isolated AI capital vault with governance layer.

CRITICAL SECURITY CONTRACT:
  - Human portfolio: STRICT READ ONLY — AI cannot touch it
  - JARVIS Capital: isolated sandbox, allocated by user, AI-governed
  - Cross-account access: IMPOSSIBLE by design (no shared broker calls)
  - Profit transfers: ALWAYS require explicit human approval (no auto-transfer)
  - Max allocation: hard-capped at $500 (user-configurable, never auto-increased)

Deployment Lifecycle:
  Phase 1 — Paper learning only
  Phase 2 — Validated behavioral learning (readiness >= 25)
  Phase 3 — Readiness threshold achieved (readiness >= 50)
  Phase 4 — Human approval required (readiness >= 70)
  Phase 5 — Micro-capital deployment (readiness >= 85, human approved)
  Phase 6 — Controlled scaling (readiness >= 95, track record established)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from opsx.capital.capital_store import capital_store, READINESS_LEVELS, _level_from_score
from opsx.capital.readiness_engine import compute_readiness, evaluate_readiness_delta

log = logging.getLogger("jarvis.capital")

DEPLOYMENT_PHASES = {
    1: {"name": "Paper Learning",          "readiness_min": 0,  "desc": "AI observes and learns from simulated trades"},
    2: {"name": "Validated Learning",      "readiness_min": 25, "desc": "Behavioral patterns validated — quality improving"},
    3: {"name": "Readiness Achieved",      "readiness_min": 50, "desc": "Consistent quality demonstrated in simulation"},
    4: {"name": "Human Approval Required", "readiness_min": 70, "desc": "Awaiting explicit human approval to proceed"},
    5: {"name": "Micro-Capital Active",    "readiness_min": 85, "desc": "Small real allocation — strictly monitored"},
    6: {"name": "Controlled Scaling",      "readiness_min": 95, "desc": "Track record established — gradual growth approved"},
}

RISK_MODES = {
    "conservative":  {"desc": "Capital preservation · low volatility · elite setups only",   "max_pos_pct": 5,  "stop_pct": 3},
    "balanced":      {"desc": "Moderate growth · controlled risk · balanced exposure",         "max_pos_pct": 10, "stop_pct": 5},
    "aggressive":    {"desc": "Higher opportunity capture · momentum · hard risk controls",    "max_pos_pct": 15, "stop_pct": 8},
    "experimental":  {"desc": "Novel strategies · paper only · never deployed to live capital","max_pos_pct": 20, "stop_pct": 10},
}

ALLOCATION_TIERS = [50.0, 100.0, 250.0, 500.0]


class JarvisCapitalOS:
    """
    JARVIS Capital governance layer.

    This class is the single authority on:
    - Capital isolation enforcement
    - Readiness computation and gating
    - Phase advancement
    - Risk mode management
    - Profit transfer approval
    """

    def get_status(self) -> Dict:
        vault  = capital_store.get_vault()
        latest = capital_store.get_latest_readiness()
        score  = float(latest["score"]) if latest else 0.0
        level, level_name = _level_from_score(score)

        phase = int(vault.get("deployment_phase", 1))
        phase_info = DEPLOYMENT_PHASES.get(phase, DEPLOYMENT_PHASES[1])
        next_phase = DEPLOYMENT_PHASES.get(phase + 1)

        risk_mode = vault.get("risk_mode", "balanced")
        risk_info = RISK_MODES.get(risk_mode, RISK_MODES["balanced"])

        sandbox_capital   = float(vault.get("sandbox_capital", 0))
        sandbox_value     = float(vault.get("sandbox_value", 0))
        realized_profit   = float(vault.get("realized_profit", 0))
        unrealized_profit = float(vault.get("unrealized_profit", 0))
        total_transfers   = float(vault.get("total_transfers", 0))
        is_active         = bool(vault.get("is_active", False))

        # Capital safety locks
        safety_locks = self._compute_safety_locks(vault, score)

        return {
            "status":            "ok",
            "is_active":         is_active,
            "sandbox_capital":   round(sandbox_capital, 2),
            "sandbox_value":     round(sandbox_value, 2),
            "realized_profit":   round(realized_profit, 2),
            "unrealized_profit": round(unrealized_profit, 2),
            "total_pnl":         round(sandbox_value - sandbox_capital, 2),
            "total_pnl_pct":     round((sandbox_value - sandbox_capital) / sandbox_capital * 100, 2) if sandbox_capital > 0 else 0,
            "total_transfers":   round(total_transfers, 2),
            "max_allocation":    float(vault.get("max_allocation", 500)),
            "allocation_tiers":  ALLOCATION_TIERS,
            "readiness": {
                "score":       score,
                "level":       level,
                "level_name":  level_name,
                "levels":      READINESS_LEVELS,
                "history":     capital_store.get_readiness_history(30),
            },
            "deployment": {
                "phase":       phase,
                "phase_name":  phase_info["name"],
                "phase_desc":  phase_info["desc"],
                "next_phase":  next_phase,
                "all_phases":  DEPLOYMENT_PHASES,
            },
            "risk_mode":    risk_mode,
            "risk_info":    risk_info,
            "all_modes":    RISK_MODES,
            "safety_locks": safety_locks,
            "allocated_at": vault.get("allocated_at"),
            "updated_at":   vault.get("updated_at"),
            "real_trade":   False,
        }

    def _compute_safety_locks(self, vault: Dict, readiness: float) -> Dict:
        """Active safety constraints based on current state."""
        return {
            "human_portfolio":    "READ_ONLY — AI cannot modify",
            "max_allocation_usd": float(vault.get("max_allocation", 500)),
            "min_readiness_live": 85,
            "current_readiness":  readiness,
            "can_deploy_real":    readiness >= 85 and bool(vault.get("is_active")),
            "experimental_paper_only": True,
            "auto_transfer":      False,
            "requires_human_approval_for": ["transfer_profits", "phase_5_deployment", "phase_6_scaling"],
        }

    def refresh_readiness(self) -> Dict:
        """Recompute readiness from accumulated learning data and persist."""
        try:
            from opsx.database.paperlab_store import store as _pls
            from opsx.memory.paperlab_memory import learning_memory as _lm
            learning_summary = _lm.get_metrics()
            strategy_stats   = _pls.get_strategy_stats()
            recent_trades    = _pls.get_trades(limit=100)
        except Exception as exc:
            log.warning("Readiness refresh: data load failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        prev_rec = capital_store.get_latest_readiness()
        prev_score = float(prev_rec["score"]) if prev_rec else 0.0

        score, reason, components = compute_readiness(
            learning_summary, strategy_stats, recent_trades
        )

        delta_info = evaluate_readiness_delta(prev_score, score, components)

        capital_store.record_readiness(
            score        = score,
            delta        = delta_info["delta"],
            reason       = reason,
            trade_quality= float(components.get("quality", 0)),
            drawdown_pct = float(components.get("drawdown_penalty", 0)),
        )

        # Auto-advance phase based on readiness
        self._try_advance_phase(score)

        _, level_name = _level_from_score(score)
        return {
            "status":      "ok",
            "score":       score,
            "prev_score":  prev_score,
            "delta":       delta_info["delta"],
            "level_name":  level_name,
            "components":  components,
            "reason":      reason,
            "messages":    delta_info["messages"],
            "real_trade":  False,
        }

    def _try_advance_phase(self, readiness: float) -> None:
        vault = capital_store.get_vault()
        phase = int(vault.get("deployment_phase", 1))
        # Only auto-advance to phases 1-3; phases 4-6 require human approval
        for p in [2, 3]:
            if phase < p and readiness >= DEPLOYMENT_PHASES[p]["readiness_min"]:
                capital_store.update_vault({"deployment_phase": p})
                log.info("JARVIS Capital: auto-advanced to Phase %d (readiness=%.1f)", p, readiness)
                phase = p
                break

    def allocate_capital(self, amount: float) -> Dict:
        if amount not in ALLOCATION_TIERS and amount != round(amount, 2):
            return {"ok": False, "error": f"Use standard tiers: {ALLOCATION_TIERS}"}
        if amount > 500:
            return {"ok": False, "error": "Hard cap: max $500 allocation"}
        return capital_store.allocate_capital(amount)

    def set_risk_mode(self, mode: str, trigger: str = "user", vix: Optional[float] = None) -> Dict:
        if mode not in RISK_MODES:
            return {"ok": False, "error": f"Invalid mode. Use: {list(RISK_MODES)}"}
        vault = capital_store.get_vault()
        prev  = vault.get("risk_mode", "balanced")
        capital_store.update_vault({"risk_mode": mode})
        capital_store.log_risk_mode(mode=mode, prev_mode=prev, trigger=trigger, vix=vix)
        log.info("Risk mode: %s → %s (trigger=%s)", prev, mode, trigger)
        return {"ok": True, "mode": mode, "prev": prev, "info": RISK_MODES[mode]}

    def request_transfer(self, amount: float, reason: str) -> Dict:
        """
        User-initiated profit transfer from JARVIS Capital → Human Portfolio.
        ALWAYS requires explicit call — never automatic.
        """
        if amount <= 0:
            return {"ok": False, "error": "Amount must be positive"}
        vault = capital_store.get_vault()
        profit = float(vault.get("realized_profit", 0))
        if profit <= 0:
            return {"ok": False, "error": "No realized profit available to transfer"}
        amount = min(amount, profit)

        try:
            from opsx.database.paperlab_store import store as _pls
            analytics = _pls.get_analytics()
        except Exception:
            analytics = {}

        result = capital_store.record_transfer(
            amount=amount,
            reason=reason or "Manual profit transfer",
            perf_snap={
                "win_rate":    analytics.get("win_rate_pct", 0),
                "total_trades": analytics.get("total_trades", 0),
                "total_pnl":   analytics.get("total_pnl", 0),
            },
        )
        if result.get("ok"):
            log.info("Profit transfer approved: $%.2f → human portfolio", amount)
        return result

    def get_vs_human(self, human_snapshot: Optional[Dict] = None) -> Dict:
        """AI vs Human performance comparison."""
        try:
            from opsx.database.paperlab_store import store as _pls
            analytics = _pls.get_analytics()
        except Exception:
            analytics = {}

        vault      = capital_store.get_vault()
        latest_r   = capital_store.get_latest_readiness()
        readiness  = float(latest_r["score"]) if latest_r else 0

        ai = {
            "total_pnl_pct": round(
                (float(vault.get("sandbox_value", 0)) - float(vault.get("sandbox_capital", 0)))
                / max(float(vault.get("sandbox_capital", 1)), 1) * 100, 2
            ),
            "win_rate":      float(analytics.get("win_rate_pct", 0)),
            "total_trades":  int(analytics.get("total_trades", 0)),
            "readiness":     readiness,
            "risk_mode":     vault.get("risk_mode", "balanced"),
        }

        human = {
            "total_pnl_pct": float((human_snapshot or {}).get("total_pnl_pct", 0)),
            "positions":     int((human_snapshot or {}).get("position_count", 0)),
            "note":          "IBKR live portfolio",
        }

        leader = "ai" if ai["total_pnl_pct"] > human["total_pnl_pct"] else "human"
        return {
            "status":  "ok",
            "ai":      ai,
            "human":   human,
            "leader":  leader,
            "real_trade": False,
        }

    def get_evolution_metrics(self) -> Dict:
        """11 AI evolution metrics for the Evolution Center."""
        try:
            from opsx.memory.paperlab_memory import learning_memory as _lm
            from opsx.database.paperlab_store import store as _pls
            learning = _lm.get_metrics()
            strategy_stats = _pls.get_strategy_stats()
            recent_trades  = _pls.get_trades(limit=50)
        except Exception:
            learning = {}
            strategy_stats = []
            recent_trades  = []

        latest_r  = capital_store.get_latest_readiness()
        readiness = float(latest_r["score"]) if latest_r else 0

        accuracy  = float(learning.get("accuracy_pct", 0))
        avg_conf  = float(learning.get("avg_confidence_pct", 0))
        lqs       = float(learning.get("learning_quality_score", 0))
        total     = int(learning.get("total_decisions", 0))

        # Market adaptation: how well does accuracy hold across regimes?
        # Approximated: if we have diverse strategies with good win rates → high adaptation
        n_strats  = len(strategy_stats)
        avg_wr    = sum(float(s.get("win_rate", 0)) for s in strategy_stats) / max(n_strats, 1)
        adaptation = min(100, avg_wr * 1.2) if n_strats >= 3 else avg_wr * 0.7

        # Risk discipline: based on drawdown control and profit factor
        best_pf = max((float(s.get("profit_factor", 0)) for s in strategy_stats), default=0)
        discipline_score = min(100, best_pf * 30 + accuracy * 0.3)

        # Strategy stability: fewer strategy switches + higher win rates = stable
        stability = min(100, (1 / max(n_strats, 1)) * 200 + avg_wr) if n_strats else 20

        # Regime understanding: approximated from recent performance vs accuracy
        regime_score = min(100, lqs * 0.9 + (10 if total >= 20 else 0))

        # Volatility adaptation: placeholder, will improve with more data
        vol_adaptation = min(100, accuracy * 0.8) if total >= 10 else accuracy * 0.5

        return {
            "readiness_score":         round(readiness, 1),
            "confidence_score":        round(avg_conf, 1),
            "learning_progress":       round(min(100, total / 50 * 30 + lqs * 0.7), 1),
            "market_adaptation":       round(adaptation, 1),
            "risk_discipline":         round(discipline_score, 1),
            "strategy_stability":      round(stability, 1),
            "regime_understanding":    round(regime_score, 1),
            "news_interpretation":     0,  # grows with options flow integration
            "volatility_adaptation":   round(vol_adaptation, 1),
            "options_understanding":   0,  # grows with options flow data
            "futures_understanding":   0,  # grows with futures data
            "total_decisions":         total,
            "recent_lessons":          learning.get("recent_lessons", []),
            "strategy_confidence":     learning.get("strategy_confidence", {}),
            "real_trade":              False,
        }


# Singleton
jarvis_capital = JarvisCapitalOS()
