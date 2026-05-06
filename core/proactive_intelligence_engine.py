"""
Proactive Intelligence Engine.

Scans JARVIS data sources and surfaces time-sensitive alerts
the user has NOT explicitly asked for — follow-up detection,
stale tasks, portfolio risk shifts, earnings awareness.

All outputs are read-only intelligence. real_trade: False always.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


_DATA_ROOT = Path("data")
_LEARNING_PATH = _DATA_ROOT / "learning" / "signal_outcomes.json"
_PORTFOLIO_PATH = _DATA_ROOT / "portfolio" / "unified_snapshot.json"
_PAPER_PATH = _DATA_ROOT / "portfolio" / "paper_positions.json"


class ProactiveIntelligenceEngine:
    """
    Generates proactive alerts by scanning portfolio, task, and communication data.

    Alert types:
    - follow_up     : email/contact with no reply > N days
    - stale_task    : task not touched in > N days
    - portfolio_risk: concentration spike, drawdown, new concentration warning
    - exposure_shift: position weight changed significantly vs last snapshot
    - earnings_soon : earnings within 7 days for held positions
    - overload      : too many high-priority open items
    - priority_drift: high tasks becoming neglected
    """

    SEVERITIES = ("critical", "high", "medium", "low")

    def scan(self, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run all proactive scans and return unified alert list.
        context: optional dict with {tasks, emails, portfolio_snapshot}
        """
        ctx = context or {}
        alerts: List[Dict] = []

        alerts.extend(self._scan_portfolio_risk(ctx.get("portfolio_snapshot")))
        alerts.extend(self._scan_exposure_shift(ctx.get("portfolio_snapshot")))
        alerts.extend(self._scan_stale_tasks(ctx.get("tasks", [])))
        alerts.extend(self._scan_follow_up(ctx.get("emails", [])))
        alerts.extend(self._scan_overload(ctx.get("tasks", [])))

        # Sort: critical first, then high, medium, low
        sev_order = {s: i for i, s in enumerate(self.SEVERITIES)}
        alerts.sort(key=lambda a: sev_order.get(a.get("severity", "low"), 99))

        return {
            "alerts":        alerts,
            "alert_count":   len(alerts),
            "critical_count": sum(1 for a in alerts if a.get("severity") == "critical"),
            "high_count":     sum(1 for a in alerts if a.get("severity") == "high"),
            "real_trade":    False,
            "generated_at":  datetime.utcnow().isoformat(),
        }

    # ── Portfolio Risk ─────────────────────────────────────────────────

    def _scan_portfolio_risk(self, portfolio: Optional[Dict]) -> List[Dict]:
        alerts = []
        if not portfolio or portfolio.get("status") == "no_data":
            # Try loading from cache
            try:
                portfolio = json.loads(_PORTFOLIO_PATH.read_text(encoding="utf-8"))
            except Exception:
                return []

        warnings = portfolio.get("concentration_warnings", [])
        total_val = portfolio.get("total_market_value", 0)
        daily_pnl = portfolio.get("total_daily_pnl", 0)
        unrealized = portfolio.get("total_unrealized_pnl", 0)

        for w in warnings:
            if w.get("type") == "single_name_concentration":
                sym = w.get("symbol", "?")
                pct = w.get("weight_pct", 0)
                alerts.append(self._alert(
                    type_="portfolio_risk",
                    severity="high" if pct > 25 else "medium",
                    title=f"{sym} concentration: {pct}%",
                    body=f"{sym} represents {pct}% of your portfolio — above safe single-name threshold.",
                    action=f"Consider trimming {sym} to below 15% of portfolio.",
                    data={"symbol": sym, "weight_pct": pct},
                ))

        if total_val > 0:
            daily_pct = daily_pnl / total_val * 100
            if daily_pct < -3:
                alerts.append(self._alert(
                    type_="portfolio_risk",
                    severity="high",
                    title=f"Portfolio down {daily_pct:.1f}% today",
                    body=f"Significant drawdown: ${daily_pnl:+,.0f} today. Review catalysts.",
                    action="Check positions for stop-loss triggers. Avoid emotional selling.",
                    data={"daily_pnl": daily_pnl, "daily_pct": daily_pct},
                ))

            unr_pct = unrealized / total_val * 100
            if unr_pct < -15:
                alerts.append(self._alert(
                    type_="portfolio_risk",
                    severity="high",
                    title=f"Unrealized loss: {unr_pct:.1f}%",
                    body=f"Total unrealized P&L is {unr_pct:.1f}% — review investment theses.",
                    action="Identify positions where thesis has fundamentally changed.",
                    data={"unrealized_pct": unr_pct},
                ))

        return alerts

    # ── Exposure Shift ─────────────────────────────────────────────────

    def _scan_exposure_shift(self, portfolio: Optional[Dict]) -> List[Dict]:
        alerts = []
        if not portfolio or portfolio.get("status") == "no_data":
            return []

        positions = portfolio.get("all_positions", [])
        total_val = portfolio.get("total_market_value", 0)
        if total_val <= 0:
            return []

        for pos in positions:
            sym = pos.get("symbol", "")
            mval = pos.get("market_value", 0)
            weight = mval / total_val * 100
            prev_weight = pos.get("prev_weight_pct")

            if prev_weight is not None:
                delta = weight - prev_weight
                if abs(delta) >= 5:
                    direction = "increased" if delta > 0 else "decreased"
                    alerts.append(self._alert(
                        type_="exposure_shift",
                        severity="medium" if abs(delta) >= 8 else "low",
                        title=f"{sym} exposure {direction} to {weight:.1f}%",
                        body=f"{sym} weight shifted {delta:+.1f}% (now {weight:.1f}% of portfolio).",
                        action=f"Review {sym} position sizing — rebalance if outside target range.",
                        data={"symbol": sym, "weight": weight, "delta": delta},
                    ))
            elif weight > 20:
                alerts.append(self._alert(
                    type_="exposure_shift",
                    severity="medium",
                    title=f"{sym} at {weight:.1f}% — elevated concentration",
                    body=f"{sym} now represents {weight:.1f}% of invested capital.",
                    action=f"Set a target weight for {sym} and rebalance if exceeded.",
                    data={"symbol": sym, "weight": weight},
                ))

        return alerts[:3]  # max 3 exposure alerts

    # ── Stale Tasks ────────────────────────────────────────────────────

    def _scan_stale_tasks(self, tasks: List[Dict]) -> List[Dict]:
        alerts = []
        now = datetime.utcnow()
        stale_threshold_days = 3

        for task in tasks:
            status = task.get("status", "").lower()
            if status in ("done", "completed", "cancelled"):
                continue

            updated = task.get("updated_at") or task.get("created_at")
            if not updated:
                continue

            try:
                last = datetime.fromisoformat(updated.replace("Z", ""))
                age_days = (now - last).days
            except Exception:
                continue

            priority = task.get("priority", "medium").lower()
            threshold = stale_threshold_days if priority in ("high", "urgent") else 7

            if age_days >= threshold:
                alerts.append(self._alert(
                    type_="stale_task",
                    severity="high" if priority in ("high", "urgent") else "medium",
                    title=f"Stale task: {(task.get('title') or task.get('text', 'Unknown'))[:50]}",
                    body=f"This {priority}-priority task hasn't been touched in {age_days} days.",
                    action="Update status, reschedule, or close this task.",
                    data={"task_id": task.get("id"), "age_days": age_days, "priority": priority},
                ))

        return alerts[:4]  # max 4 stale task alerts

    # ── Follow-up Detection ────────────────────────────────────────────

    def _scan_follow_up(self, emails: List[Dict]) -> List[Dict]:
        alerts = []
        now = datetime.utcnow()
        follow_up_days = 3

        for email in emails:
            if email.get("replied") or email.get("isRead") is False:
                # Only flag read emails we haven't replied to
                if email.get("isRead") is False:
                    continue

            sender = email.get("from") or email.get("sender", "")
            subject = email.get("subject", "")
            received = email.get("receivedDateTime") or email.get("received")

            if not received or not sender:
                continue

            try:
                recv_dt = datetime.fromisoformat(received.replace("Z", "").split("+")[0])
                age_days = (now - recv_dt).days
            except Exception:
                continue

            if age_days >= follow_up_days and not email.get("replied"):
                alerts.append(self._alert(
                    type_="follow_up",
                    severity="medium",
                    title=f"No reply to {sender[:40]} in {age_days}d",
                    body=f"Email from {sender}: '{subject[:60]}' — {age_days} days without reply.",
                    action=f"Reply to {sender} or archive if not relevant.",
                    data={"from": sender, "subject": subject, "age_days": age_days},
                ))

        return alerts[:3]  # max 3 follow-up alerts

    # ── Overload Detection ─────────────────────────────────────────────

    def _scan_overload(self, tasks: List[Dict]) -> List[Dict]:
        high_open = [
            t for t in tasks
            if t.get("priority", "").lower() in ("high", "urgent")
            and t.get("status", "").lower() not in ("done", "completed", "cancelled")
        ]
        if len(high_open) >= 5:
            return [self._alert(
                type_="overload",
                severity="medium",
                title=f"{len(high_open)} high-priority tasks open",
                body=f"You have {len(high_open)} high/urgent tasks open simultaneously — focus risk.",
                action="Close or defer 2–3 tasks to maintain focus on what matters most.",
                data={"high_open_count": len(high_open)},
            )]
        return []

    # ── Helper ─────────────────────────────────────────────────────────

    def _alert(
        self,
        type_: str,
        severity: str,
        title: str,
        body: str,
        action: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return {
            "type":       type_,
            "severity":   severity,
            "title":      title,
            "body":       body,
            "action":     action,
            "data":       data or {},
            "timestamp":  datetime.utcnow().isoformat(),
        }


# Singleton
proactive_intelligence = ProactiveIntelligenceEngine()
