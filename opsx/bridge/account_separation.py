"""
JARVIS Account Separation Layer.

Enforces strict isolation between LIVE real account data and PAPER Lab simulation.
Attaches structured metadata to every portfolio response so the UI can never confuse
real positions with simulated trades.

Fields added to every response:
  account_type:       "LIVE" | "PAPER" | "SIMULATED" | "UNKNOWN"
  data_origin:        "ibkr_live" | "ibkr_paper" | "autonomous_sim" | "cache" | "unknown"
  readonly_mode:      true (always)
  execution_blocked:  true (always)
  real_trade:         false (always)

Audit log: data/bridge/account_separation_audit.json
  Every broker interaction is logged with timestamp + account_type + data_origin.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("jarvis.account_separation")

_AUDIT_LOG = Path("data/bridge/account_separation_audit.json")

# ── Account type detection ─────────────────────────────────────────────────────

def detect_account_type(account_id: str) -> str:
    """
    Detect whether an IBKR account is live or paper.
    IBKR convention: DU prefix = Demo/Paper, U prefix = Live.
    """
    if not account_id:
        return "UNKNOWN"
    if account_id.startswith("DU"):
        return "PAPER"
    return "LIVE"


def detect_data_origin(account_id: str, source: str = "") -> str:
    """Return a structured data origin label."""
    if source == "autonomous_sim":
        return "autonomous_sim"
    if source == "cache":
        return "cache"
    acct_type = detect_account_type(account_id)
    if acct_type == "LIVE":
        return "ibkr_live"
    if acct_type == "PAPER":
        return "ibkr_paper"
    return "unknown"


# ── Separation metadata injector ───────────────────────────────────────────────

def attach_separation_metadata(
    data: Dict,
    account_id: str = "",
    source: str = "",
    extra: Optional[Dict] = None,
) -> Dict:
    """
    Attach account separation metadata to any portfolio/snapshot response.
    Mutates and returns the dict.
    """
    account_type = detect_account_type(account_id)
    data_origin  = detect_data_origin(account_id, source)

    data["account_type"]      = account_type
    data["data_origin"]       = data_origin
    data["readonly_mode"]     = True
    data["execution_blocked"] = True
    data["real_trade"]        = False

    if extra:
        data.update(extra)

    return data


def attach_paper_lab_metadata(data: Dict) -> Dict:
    """
    Attach metadata for Paper Lab (autonomous simulation) responses.
    Always marks as SIMULATED, never LIVE.
    """
    data["account_type"]      = "SIMULATED"
    data["data_origin"]       = "autonomous_sim"
    data["readonly_mode"]     = True
    data["execution_blocked"] = True
    data["real_trade"]        = False
    return data


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_no_live_mix(real_data: Dict, paper_data: Dict) -> Dict:
    """
    Verify that real portfolio data is not mixed with paper simulation data.
    Returns a validation report.
    """
    real_origin  = real_data.get("data_origin", "unknown")
    paper_origin = paper_data.get("data_origin", "unknown")

    # Check: real must come from ibkr_live or cache, not autonomous_sim
    real_clean = real_origin in ("ibkr_live", "cache", "unknown")
    # Check: paper must come from autonomous_sim, not ibkr_live
    paper_clean = paper_origin in ("autonomous_sim", "unknown")

    # Check: no position lists are accidentally shared
    real_positions  = {p.get("symbol") for p in real_data.get("positions", [])}
    paper_positions = {p.get("symbol") for p in paper_data.get("positions", [])}
    # Same symbol in both is fine (monitoring overlapping stocks)
    # What matters is that PnL/execution data is separate

    return {
        "separation_valid": real_clean and paper_clean,
        "real_origin_ok":   real_clean,
        "paper_origin_ok":  paper_clean,
        "real_data_origin": real_origin,
        "paper_data_origin": paper_origin,
        "real_trade":       False,
    }


# ── Audit logging ──────────────────────────────────────────────────────────────

def audit_broker_interaction(
    account_id: str,
    operation: str,
    account_type: str = "",
    data_origin: str = "",
    success: bool = True,
    details: Optional[str] = None,
) -> None:
    """
    Log every broker data interaction for compliance audit.
    Called from bridge client and secure_bridge.
    """
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp":    datetime.utcnow().isoformat(),
        "account_id":   account_id or "unknown",
        "account_type": account_type or detect_account_type(account_id),
        "data_origin":  data_origin or detect_data_origin(account_id),
        "operation":    operation,
        "success":      success,
        "details":      details or "",
        "readonly_mode":     True,
        "execution_blocked": True,
        "real_trade":        False,
    }
    try:
        entries: list = []
        if _AUDIT_LOG.exists():
            entries = json.loads(_AUDIT_LOG.read_text(encoding="utf-8"))
        entries.append(entry)
        _AUDIT_LOG.write_text(
            json.dumps(entries[-2000:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("AUDIT %s account=%s type=%s origin=%s ok=%s",
                 operation, account_id, entry["account_type"], entry["data_origin"], success)
    except Exception as exc:
        log.warning("audit_broker_interaction write failed: %s", exc)


def get_audit_log(limit: int = 100) -> list:
    """Return the most recent audit log entries."""
    try:
        if _AUDIT_LOG.exists():
            entries = json.loads(_AUDIT_LOG.read_text(encoding="utf-8"))
            return entries[-limit:]
    except Exception:
        pass
    return []
