"""
Production-safe IBKR socket connection manager.

Centralizes:
- IBKR_URL precedence over IBKR_HOST / IBKR_PORT
- hosted-runtime localhost rejection
- TCP reachability probe before ib_insync connect()
- read-only singleton lifecycle
- reconnect state, backoff, jitter, and circuit breaker metadata

This module never exposes execution methods and always connects readonly=True.
"""
from __future__ import annotations

import logging
import random
import socket
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import os

log = logging.getLogger("jarvis.ibkr_manager")


FORBIDDEN_HOSTED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
HOSTED_ERROR = "Hosted runtime cannot connect to local IBKR directly. Use IBKR_URL/ngrok bridge."


def is_hosted_runtime() -> bool:
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_STATIC_URL")
        or os.getenv("RAILWAY_PUBLIC_DOMAIN")
        or os.getenv("ENV", "").lower() in {"production", "prod"}
    )


def _clean_host(host: str) -> str:
    return (host or "").strip().strip("[]").lower()


@dataclass(frozen=True)
class IBKRTarget:
    host: str
    port: int
    transport: str
    mode: str
    source: str
    client_id: int

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_ibkr_target(role: str = "connector") -> IBKRTarget:
    """
    Resolve the effective socket target. IBKR_URL always wins.

    Supported URL forms:
    - tcp://host:port
    - host:port
    """
    role_key = (role or "connector").upper()
    default_client_id = 10 if role == "worker" else 1
    role_env_key = f"IBKR_{role_key}_CLIENT_ID"
    if os.getenv(role_env_key):
        client_id = int(os.getenv(role_env_key))
    elif os.getenv("IBKR_CLIENT_ID"):
        log.warning(
            "IBKR_CLIENT_ID shared fallback used for role=%s — set %s to avoid clientId collision",
            role, role_env_key,
        )
        client_id = int(os.getenv("IBKR_CLIENT_ID"))
    else:
        client_id = default_client_id

    ibkr_url = (os.getenv("IBKR_URL") or "").strip()
    if ibkr_url:
        parsed = urlparse(ibkr_url if "://" in ibkr_url else f"tcp://{ibkr_url}")
        if not parsed.hostname or not parsed.port:
            raise EnvironmentError("IBKR_URL must be tcp://<host>:<port> or <host>:<port>.")
        target = IBKRTarget(
            host=parsed.hostname,
            port=int(parsed.port),
            transport=parsed.scheme or "tcp",
            mode="remote_bridge" if is_hosted_runtime() else "local_url",
            source="IBKR_URL",
            client_id=client_id,
        )
    else:
        target = IBKRTarget(
            host=os.getenv("IBKR_HOST", "127.0.0.1"),
            port=int(os.getenv("IBKR_PORT", "4001")),
            transport="tcp",
            mode="local" if not is_hosted_runtime() else "invalid_hosted_local",
            source="IBKR_HOST_PORT",
            client_id=client_id,
        )

    validate_ibkr_target(target)
    return target


def validate_ibkr_target(target: IBKRTarget) -> None:
    if is_hosted_runtime() and _clean_host(target.host) in FORBIDDEN_HOSTED_HOSTS:
        raise EnvironmentError(HOSTED_ERROR)


def tcp_probe(host: str, port: int, timeout: float = 3.0) -> Dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return {
                "reachable": True,
                "host": host,
                "port": int(port),
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            }
    except Exception as exc:
        return {
            "reachable": False,
            "host": host,
            "port": int(port),
            "error": str(exc),
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        }


class IBKRConnectionManager:
    def __init__(self, role: str = "connector", max_failures: int = 5, max_backoff: int = 120) -> None:
        self.role = role
        self._lock = threading.RLock()
        self._ib: Optional[Any] = None
        self._account = ""
        self._state = "disconnected"
        self._last_successful_connect: Optional[str] = None
        self._last_error: Optional[str] = None
        self._reconnect_attempts = 0
        self._consecutive_failures = 0
        self._circuit_opened_at: Optional[str] = None
        self._max_failures = max_failures
        self._max_backoff = max_backoff
        self._last_probe: Dict[str, Any] = {}
        self._target = resolve_ibkr_target(role)

    @property
    def ib(self) -> Optional[Any]:
        with self._lock:
            return self._ib

    @property
    def account(self) -> str:
        with self._lock:
            return self._account

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(self._ib and self._state == "connected" and self._ib.isConnected())

    def target(self) -> IBKRTarget:
        with self._lock:
            self._target = resolve_ibkr_target(self.role)
            return self._target

    def connect(self, timeout: float = 10.0) -> Dict[str, Any]:
        with self._lock:
            target = self.target()
            if self._state == "circuit_open":
                return self._failure("circuit_open", "IBKR circuit breaker is open", target)
            if self._ib and self._ib.isConnected():
                self._state = "connected"
                return self._success(target, reused=True)

            self._state = "connecting"
            probe = tcp_probe(target.host, target.port, timeout=min(float(timeout), 4.0))
            self._last_probe = probe
            if not probe["reachable"]:
                self._register_failure(probe.get("error", "tcp probe failed"))
                return self._failure("unreachable", probe.get("error", "tcp probe failed"), target)

            try:
                from ib_insync import IB, util
                util.logToConsole(logging.WARNING)
                # Cleanly close stale socket before creating a new IB() instance
                if self._ib is not None:
                    try:
                        self._ib.disconnect()
                    except Exception:
                        pass
                    self._ib = None
                ib = IB()
                ib.connect(
                    target.host,
                    target.port,
                    clientId=target.client_id,
                    readonly=True,
                    timeout=timeout,
                )
                accounts = ib.managedAccounts()
                self._ib = ib
                self._account = accounts[0] if accounts else ""
                self._state = "connected"
                self._last_successful_connect = datetime.utcnow().isoformat()
                self._last_error = None
                self._consecutive_failures = 0
                self._circuit_opened_at = None
                log.info(
                    "IBKR Gateway connected: role=%s host=%s port=%d clientId=%d account=%s",
                    self.role, target.host, target.port, target.client_id, self._account,
                )
                return self._success(target, reused=False)
            except Exception as exc:
                self._ib = None
                self._account = ""
                self._register_failure(str(exc))
                return self._failure("connect_failed", str(exc), target)

    def disconnect(self) -> Dict[str, Any]:
        with self._lock:
            if self._ib:
                try:
                    self._ib.disconnect()
                except Exception:
                    pass
            self._ib = None
            self._account = ""
            self._state = "disconnected"
            return {"status": "disconnected", "real_trade": False}

    def reset_circuit(self) -> None:
        """
        Manually reset a tripped circuit breaker so reconnect attempts resume.
        Call after a known Gateway maintenance window or scheduled restart.
        """
        with self._lock:
            if self._state == "circuit_open":
                log.info("IBKR circuit breaker reset (role=%s)", self.role)
            self._state = "disconnected"
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def mark_degraded(self, error: str = "") -> None:
        with self._lock:
            self._register_failure(error or "degraded")

    def reconnect_delay(self) -> float:
        with self._lock:
            base = min(2 ** max(self._consecutive_failures - 1, 0), self._max_backoff)
            return round(base + random.uniform(0, min(1.5, base * 0.25)), 2)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            target = self._target
            return {
                "state": self._state,
                "connected": self.connected,
                "mode": target.mode,
                "target_host": target.host,
                "target_port": target.port,
                "transport": target.transport,
                "target_source": target.source,
                "active_client_id": target.client_id,
                "account": self._account,
                "last_successful_connect": self._last_successful_connect,
                "reconnect_attempts": self._reconnect_attempts,
                "consecutive_failures": self._consecutive_failures,
                "circuit_state": "open" if self._state == "circuit_open" else "closed",
                "circuit_opened_at": self._circuit_opened_at,
                "last_error": self._last_error,
                "last_probe": self._last_probe,
                "retry_delay": self.reconnect_delay(),
                "readonly": True,
                "execution_blocked": True,
                "real_trade": False,
            }

    def _register_failure(self, error: str) -> None:
        self._reconnect_attempts += 1
        self._consecutive_failures += 1
        self._last_error = error
        self._state = "circuit_open" if self._consecutive_failures >= self._max_failures else "degraded"
        if self._state == "circuit_open" and not self._circuit_opened_at:
            self._circuit_opened_at = datetime.utcnow().isoformat()

    def _success(self, target: IBKRTarget, reused: bool) -> Dict[str, Any]:
        return {
            "status": "connected",
            "connected": True,
            "reused": reused,
            "account": self._account,
            "host": target.host,
            "port": target.port,
            "mode": target.mode,
            "transport": target.transport,
            "active_client_id": target.client_id,
            "readonly": True,
            "execution_blocked": True,
            "real_trade": False,
            "connected_at": self._last_successful_connect or datetime.utcnow().isoformat(),
        }

    def _failure(self, status: str, error: str, target: IBKRTarget) -> Dict[str, Any]:
        return {
            "status": status,
            "connected": False,
            "error": error,
            "target_host": target.host,
            "target_port": target.port,
            "mode": target.mode,
            "transport": target.transport,
            "active_client_id": target.client_id,
            "retry_delay": self.reconnect_delay(),
            "readonly": True,
            "execution_blocked": True,
            "real_trade": False,
        }


_MANAGERS: Dict[str, IBKRConnectionManager] = {}
_MANAGERS_LOCK = threading.RLock()


def get_ibkr_manager(role: str = "connector") -> IBKRConnectionManager:
    with _MANAGERS_LOCK:
        key = role or "connector"
        if key not in _MANAGERS:
            _MANAGERS[key] = IBKRConnectionManager(role=key)
        return _MANAGERS[key]
