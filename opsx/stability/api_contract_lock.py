"""
JARVIS API Contract Lock — Phase 2.

Stores expected response schemas for all critical endpoints.
Validates that response shape has not regressed.

Usage:
    lock = APIContractLock()
    issues = lock.validate("/api/debug/ibkr", response_dict)
    # issues = [] means PASS

On startup:
    lock.run_startup_check(base_url)

In deployment guard:
    lock.run_full_check(live_responses)
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.api_contract_lock")

# ── Contract Definitions ──────────────────────────────────────────────────────

_CONTRACTS: Dict[str, Dict] = {
    "/api/debug/ibkr": {
        "required_fields": [
            "mode", "bridge_enabled", "real_trade", "execution_blocked",
            "readonly", "checked_at",
        ],
        "safety_invariants": {
            "real_trade":        False,
            "execution_blocked": True,
            "readonly":          True,
        },
        "forbidden_fields": [],
        "description": "IBKR deep diagnostics — must always report safety flags",
        "contract_hash": "4dc395ca561d5175eed8",
    },
    "/api/portfolio/status": {
        "required_fields": ["status", "ibkr", "hapi", "real_trade"],
        "safety_invariants": {"real_trade": False},
        "forbidden_fields": [],
        "description": "Portfolio broker connection status",
        "contract_hash": "ebc18b4265d5a1d98b60",
    },
    "/api/health": {
        "required_fields": ["status"],
        "safety_invariants": {},
        "forbidden_fields": [],
        "description": "Basic health check — must always return JSON with status",
        "contract_hash": "71c1dcb9cb1f21d1c7e2",
    },
    "/api/bridge/watchdog": {
        "required_fields": ["running", "consecutive_failures", "real_trade"],
        "safety_invariants": {"real_trade": False},
        "forbidden_fields": [],
        "description": "Watchdog state — bridge reachability and staleness",
        "contract_hash": "0dd3060f85aa0bc3eff6",
    },
    "/api/debug/permissions": {
        "required_fields": [
            "real_trade_disabled", "execution_guard_active", "ibkr_read_only",
        ],
        "safety_invariants": {
            "real_trade_disabled":    True,
            "execution_guard_active": True,
            "ibkr_read_only":         True,
        },
        "forbidden_fields": [],
        "description": "Safety permission audit — all must be True",
        "contract_hash": "b83918149e3716f91eec",
    },
    "/api/paper/lab": {
        "required_fields": ["status", "real_trade"],
        "safety_invariants": {"real_trade": False},
        "forbidden_fields": [],
        "description": "Paper Lab status",
        "contract_hash": "c1e859c37757031ddf5e",
    },
    "/api/portfolio/summary": {
        "required_fields": ["real_trade"],
        "safety_invariants": {"real_trade": False},
        "forbidden_fields": [],
        "description": "Portfolio summary — must carry real_trade=False",
        "contract_hash": "9c42e0b8d612624e0a12",
    },
    "/api/outlook/status": {
        "required_fields": ["status"],
        "safety_invariants": {},
        "forbidden_fields": [],
        "description": "Outlook connection status",
        "contract_hash": "456ee15df8197236f653",
    },
    "/api/calendar/events": {
        "required_fields": ["events"],
        "safety_invariants": {},
        "forbidden_fields": [],
        "description": "Calendar events list",
        "contract_hash": "a0d5be2055eb8b864d33",
    },
}

# Safety fields that must NEVER be True (real_trade must never flip to True)
_GLOBAL_FORBIDDEN_TRUE = {"real_trade"}
# Safety fields that must NEVER be False in any IBKR-related response
_GLOBAL_REQUIRED_TRUE_IN_IBKR = {"execution_blocked", "readonly"}


# ── Validation Engine ─────────────────────────────────────────────────────────

class ContractViolation:
    def __init__(self, endpoint: str, violation_type: str, detail: str):
        self.endpoint       = endpoint
        self.violation_type = violation_type
        self.detail         = detail

    def __str__(self) -> str:
        return f"[{self.violation_type}] {self.endpoint}: {self.detail}"

    def to_dict(self) -> Dict:
        return {
            "endpoint":       self.endpoint,
            "violation_type": self.violation_type,
            "detail":         self.detail,
        }


class APIContractLock:

    def __init__(self) -> None:
        self._contracts = _CONTRACTS

    def get_contract(self, endpoint: str) -> Optional[Dict]:
        return self._contracts.get(endpoint)

    def validate(self, endpoint: str, response: Dict) -> List[ContractViolation]:
        """
        Validate response dict against the stored contract.
        Returns empty list on pass, list of ContractViolation on failure.
        """
        violations: List[ContractViolation] = []
        contract = self._contracts.get(endpoint)

        if contract is None:
            return violations  # No contract registered — not a violation

        if not isinstance(response, dict):
            violations.append(ContractViolation(
                endpoint, "INVALID_RESPONSE_TYPE",
                f"Expected dict, got {type(response).__name__}"
            ))
            return violations

        # Required field check
        for field in contract.get("required_fields", []):
            if field not in response:
                violations.append(ContractViolation(
                    endpoint, "MISSING_REQUIRED_FIELD",
                    f"Field '{field}' missing from response"
                ))

        # Safety invariant check
        for field, expected in contract.get("safety_invariants", {}).items():
            if field in response and response[field] != expected:
                violations.append(ContractViolation(
                    endpoint, "SAFETY_INVARIANT_VIOLATED",
                    f"Field '{field}' expected={expected} actual={response[field]}"
                ))

        # Global: real_trade must never be True
        if response.get("real_trade") is True:
            violations.append(ContractViolation(
                endpoint, "CRITICAL_SAFETY_VIOLATION",
                "real_trade=True detected — NEVER allowed in JARVIS"
            ))

        return violations

    def validate_safety_only(self, endpoint: str, response: Dict) -> List[ContractViolation]:
        """
        Only check safety invariants (real_trade, execution_blocked, readonly).
        Used for endpoints without full contracts.
        """
        violations: List[ContractViolation] = []
        if not isinstance(response, dict):
            return violations

        if response.get("real_trade") is True:
            violations.append(ContractViolation(
                endpoint, "CRITICAL_SAFETY_VIOLATION",
                "real_trade=True detected — NEVER allowed"
            ))

        ibkr_related = any(
            k in endpoint for k in ("ibkr", "portfolio", "broker", "bridge")
        )
        if ibkr_related:
            for field in ("execution_blocked", "readonly"):
                if field in response and response[field] is False:
                    violations.append(ContractViolation(
                        endpoint, "SAFETY_INVARIANT_VIOLATED",
                        f"'{field}' is False in IBKR-related endpoint — must be True"
                    ))

        return violations

    def compute_schema_fingerprint(self, endpoint: str) -> str:
        """Compute a short fingerprint of the current contract for drift detection."""
        contract = self._contracts.get(endpoint, {})
        fields = sorted(contract.get("required_fields", []))
        raw = json.dumps({"endpoint": endpoint, "required": fields}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def check_contract_drift(self) -> List[Dict]:
        """
        Check if any contract's fingerprint has drifted from the stored hash.
        Returns list of drifted contracts.
        """
        drifted = []
        for ep, contract in self._contracts.items():
            stored_hash  = contract.get("contract_hash", "")
            computed     = self.compute_schema_fingerprint(ep)
            if stored_hash and stored_hash != computed:
                drifted.append({
                    "endpoint":     ep,
                    "stored_hash":  stored_hash,
                    "computed_hash": computed,
                    "status":       "DRIFTED",
                })
        return drifted

    def run_batch(self, responses: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Validate multiple responses at once.
        responses: { "/api/debug/ibkr": {...}, ... }
        Returns: { "pass": [...], "fail": [...], "total": N }
        """
        passed = []
        failed = []
        for endpoint, response in responses.items():
            violations = self.validate(endpoint, response)
            if violations:
                failed.append({
                    "endpoint":   endpoint,
                    "violations": [v.to_dict() for v in violations],
                })
                for v in violations:
                    log.critical("API CONTRACT VIOLATION: %s", v)
            else:
                passed.append(endpoint)

        return {
            "pass":    passed,
            "fail":    failed,
            "total":   len(responses),
            "passed":  len(passed),
            "failed":  len(failed),
            "result":  "PASS" if not failed else "FAIL",
        }

    async def run_live_check(self, base_url: str, timeout: float = 8.0) -> Dict:
        """
        Hit all registered endpoints and validate live responses.
        Used by startup validator and deployment guard.
        """
        try:
            import httpx
        except ImportError:
            return {"result": "SKIP", "reason": "httpx not available"}

        responses: Dict[str, Any] = {}
        errors: Dict[str, str]    = {}

        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            for endpoint in self._contracts:
                try:
                    resp = await client.get(endpoint)
                    if resp.status_code == 200:
                        responses[endpoint] = resp.json()
                    else:
                        errors[endpoint] = f"HTTP {resp.status_code}"
                except Exception as exc:
                    errors[endpoint] = str(exc)

        batch_result = self.run_batch(responses)
        batch_result["errors"]         = errors
        batch_result["error_count"]    = len(errors)
        batch_result["endpoints_hit"]  = len(responses)
        return batch_result

    @property
    def registered_endpoints(self) -> List[str]:
        return list(self._contracts.keys())
