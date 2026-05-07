"""
JARVIS Production Safety Rules — Phase 4.

Runtime enforcement of the 8 production invariants:

  1. Hosted runtime may NEVER call localhost
  2. LIVE and PAPER may NEVER mix
  3. real_trade must ALWAYS remain False
  4. execution_blocked must ALWAYS remain True
  5. readonly must ALWAYS remain True in LIVE context
  6. No execution path may activate
  7. Stale snapshots must be visible (never silently return stale as fresh)
  8. Bridge disconnects must surface immediately (not return empty zeros)

Each rule has:
  - check(...)   — returns True if rule passes, False if violated
  - enforce(...) — raises RuleViolation if violated
  - describe()   — human-readable description
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger("jarvis.production_rules")

_LOCALHOST_PATTERNS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


class RuleViolation(RuntimeError):
    """Raised when a production safety rule is violated at runtime."""
    def __init__(self, rule_id: str, detail: str):
        self.rule_id = rule_id
        self.detail  = detail
        super().__init__(f"[RULE:{rule_id}] {detail}")


class ProductionRules:
    """
    Singleton-friendly collection of production safety rules.
    All rules are stateless — safe to call from any thread.
    """

    # ── Rule 1: No Localhost in Production ────────────────────────────────────

    def check_no_localhost(self, url: str) -> bool:
        """Return True if URL is safe (no localhost patterns in production)."""
        if not url:
            return True
        url_lower = url.lower()
        if any(p in url_lower for p in _LOCALHOST_PATTERNS):
            return not self._is_hosted()
        return True

    def enforce_no_localhost(self, url: str, context: str = "") -> None:
        if not self.check_no_localhost(url):
            raise RuleViolation(
                "RULE_1_NO_LOCALHOST",
                f"Localhost URL '{url}' used in production context. "
                f"Context: {context or 'unknown'}. "
                "Use a public ngrok URL for IBKR_BRIDGE_URL.",
            )

    # ── Rule 2: LIVE/PAPER Never Mix ──────────────────────────────────────────

    def check_live_paper_separation(
        self,
        account_id: str,
        data_origin: str,
        panel_label: str,
    ) -> bool:
        """
        LIVE account data must only appear in LIVE-labeled panels.
        PAPER data must only appear in PAPER-labeled panels.
        """
        is_live   = account_id and not account_id.startswith("DU")
        is_paper  = account_id and account_id.startswith("DU")
        in_paper_panel = "paper" in panel_label.lower() or "lab" in panel_label.lower()
        in_live_panel  = "live" in panel_label.lower() or "cockpit" in panel_label.lower()

        if is_live and in_paper_panel:
            return False
        if is_paper and in_live_panel:
            return False
        return True

    def enforce_live_paper_separation(
        self, account_id: str, data_origin: str, panel_label: str
    ) -> None:
        if not self.check_live_paper_separation(account_id, data_origin, panel_label):
            raise RuleViolation(
                "RULE_2_LIVE_PAPER_MIX",
                f"Account '{account_id}' (origin={data_origin}) appeared in "
                f"panel '{panel_label}' — LIVE and PAPER data must never mix.",
            )

    # ── Rule 3: real_trade Always False ───────────────────────────────────────

    def check_real_trade_false(self, response: Dict) -> bool:
        return response.get("real_trade") is not True

    def enforce_real_trade_false(self, response: Dict, context: str = "") -> None:
        if not self.check_real_trade_false(response):
            raise RuleViolation(
                "RULE_3_REAL_TRADE_FALSE",
                f"real_trade=True detected in response. Context: {context}. "
                "JARVIS must NEVER execute real trades.",
            )

    # ── Rule 4: execution_blocked Always True ─────────────────────────────────

    def check_execution_blocked(self, response: Dict) -> bool:
        if "execution_blocked" not in response:
            return True  # Field absence is OK — it's not set to False
        return response["execution_blocked"] is True

    def enforce_execution_blocked(self, response: Dict, context: str = "") -> None:
        if not self.check_execution_blocked(response):
            raise RuleViolation(
                "RULE_4_EXECUTION_BLOCKED",
                f"execution_blocked=False detected. Context: {context}. "
                "Execution must remain permanently blocked.",
            )

    # ── Rule 5: readonly Always True in LIVE ──────────────────────────────────

    def check_readonly_in_live(self, response: Dict) -> bool:
        account_id = response.get("account_id", response.get("account", ""))
        is_live    = account_id and not str(account_id).startswith("DU")
        if is_live and "readonly" in response:
            return response["readonly"] is True
        return True

    def enforce_readonly_in_live(self, response: Dict, context: str = "") -> None:
        if not self.check_readonly_in_live(response):
            raise RuleViolation(
                "RULE_5_READONLY_LIVE",
                f"readonly=False for LIVE account. Context: {context}. "
                "LIVE accounts must always be read-only.",
            )

    # ── Rule 6: No Execution Path ─────────────────────────────────────────────

    _EXECUTION_METHOD_NAMES = frozenset({
        "place_order", "placeOrder", "cancel_order", "cancelOrder",
        "modify_order", "modifyOrder", "transmit_order", "execute_trade",
        "reqGlobalCancel", "reqExecutions",
    })

    def check_no_execution_call(self, method_name: str) -> bool:
        return method_name not in self._EXECUTION_METHOD_NAMES

    def enforce_no_execution_call(self, method_name: str, context: str = "") -> None:
        if not self.check_no_execution_call(method_name):
            raise RuleViolation(
                "RULE_6_NO_EXECUTION",
                f"Execution method '{method_name}' called. Context: {context}. "
                "JARVIS is permanently READ-ONLY.",
            )

    # ── Rule 7: Stale Snapshots Must Be Visible ───────────────────────────────

    def check_stale_snapshot_flagged(self, response: Dict) -> bool:
        """
        If response was built from a stale snapshot, it must carry _stale=True.
        A response with _stale not set is OK (fresh).
        A response with _stale=False is OK (explicitly fresh).
        A response with _stale=True but no stale indicator anywhere is a violation.
        """
        stale = response.get("_stale", False)
        if stale:
            return bool(response.get("_stale_reason") or response.get("stale_detected"))
        return True

    def enforce_stale_snapshot_flagged(self, response: Dict, context: str = "") -> None:
        if not self.check_stale_snapshot_flagged(response):
            raise RuleViolation(
                "RULE_7_STALE_VISIBLE",
                f"Response has _stale=True but no _stale_reason. Context: {context}. "
                "Stale data must always include a reason string.",
            )

    # ── Rule 8: Bridge Disconnects Surface Immediately ────────────────────────

    def check_bridge_disconnect_surfaced(self, response: Dict) -> bool:
        """
        If bridge is disconnected, the response must not silently show zeros.
        It must carry status='disconnected' or _stale=True.
        """
        status  = response.get("status", "")
        stale   = response.get("_stale", False)
        # If positions=[] and no status/stale hint, might be silent failure
        if (status == "disconnected" or stale or
                status in ("not_configured", "bridge_offline")):
            return True
        # No disconnection indicator — check if it looks like a silent zero
        positions = response.get("positions")
        if positions == [] and status not in ("connected", "ok", ""):
            return False  # Looks like silent empty response
        return True

    def enforce_bridge_disconnect_surfaced(self, response: Dict, context: str = "") -> None:
        if not self.check_bridge_disconnect_surfaced(response):
            raise RuleViolation(
                "RULE_8_BRIDGE_DISCONNECT",
                f"Bridge disconnection not surfaced in response. Context: {context}. "
                "Disconnects must carry status='disconnected' or _stale=True.",
            )

    # ── Batch: run all rules on a single response ─────────────────────────────

    def run_all(self, response: Dict, context: str = "") -> List[str]:
        """
        Run all applicable rules against a response dict.
        Returns list of violation messages. Empty = PASS.
        """
        violations = []
        checks = [
            ("real_trade_false",          lambda: self.check_real_trade_false(response)),
            ("execution_blocked",         lambda: self.check_execution_blocked(response)),
            ("readonly_in_live",          lambda: self.check_readonly_in_live(response)),
            ("stale_snapshot_flagged",    lambda: self.check_stale_snapshot_flagged(response)),
            ("bridge_disconnect_surfaced",lambda: self.check_bridge_disconnect_surfaced(response)),
        ]
        for rule_id, check_fn in checks:
            try:
                if not check_fn():
                    msg = f"RULE FAILED: {rule_id} — context={context}"
                    violations.append(msg)
                    log.critical(msg)
            except Exception as exc:
                violations.append(f"RULE ERROR: {rule_id} — {exc}")
        return violations

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_hosted() -> bool:
        return bool(
            os.getenv("RAILWAY_ENVIRONMENT")
            or os.getenv("RAILWAY_SERVICE_ID")
            or os.getenv("RAILWAY_PROJECT_ID")
            or os.getenv("RAILWAY_STATIC_URL")
            or os.getenv("RAILWAY_PUBLIC_DOMAIN")
            or os.getenv("ENV", "").lower() in {"production", "prod"}
        )


# Module-level singleton
rules = ProductionRules()
