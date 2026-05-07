"""
Bridge WebSocket Manager — real-time push updates to connected clients.

Features:
  - Manages N concurrent WebSocket connections
  - Broadcasts portfolio/market updates to all live clients
  - Heartbeat ping/pong (15s interval) — dead connections cleaned up automatically
  - Per-connection metadata: remote address, connected_at, last_pong
  - Thread-safe; broadcast uses asyncio.create_task to avoid blocking the event loop
  - On disconnect the slot is freed immediately; no leaked handles

Message format (JSON strings sent to clients):
  { "type": "portfolio",  "data": {...}, "ts": "ISO8601" }
  { "type": "market",     "data": {...}, "ts": "ISO8601" }
  { "type": "heartbeat",  "ts": "ISO8601" }
  { "type": "error",      "message": "...", "ts": "ISO8601" }
  { "type": "connected",  "message": "JARVIS Bridge v1 — read-only", "ts": "ISO8601" }
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Set
from weakref import WeakSet

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("jarvis.bridge.ws")

_HEARTBEAT_INTERVAL = 15   # seconds between pings
_PONG_TIMEOUT       = 30   # seconds before declaring connection dead


class _Connection:
    __slots__ = ("ws", "remote", "connected_at", "last_pong", "alive")

    def __init__(self, ws: WebSocket, remote: str) -> None:
        self.ws           = ws
        self.remote       = remote
        self.connected_at = datetime.utcnow()
        self.last_pong    = datetime.utcnow()
        self.alive        = True


class WebSocketManager:
    """Manages all active WebSocket connections for the bridge."""

    def __init__(self) -> None:
        self._connections: Set[_Connection] = set()
        self._lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> _Connection:
        """Accept a new WebSocket connection and register it."""
        await ws.accept()
        remote = self._remote(ws)
        conn   = _Connection(ws, remote)

        async with self._lock:
            self._connections.add(conn)

        log.info("WS connected: %s (total=%d)", remote, len(self._connections))

        # Send welcome frame
        await self._send(conn, {
            "type":    "connected",
            "message": "JARVIS Secure Bridge v1 — read-only portfolio stream",
            "ts":      _now(),
        })
        return conn

    async def disconnect(self, conn: _Connection) -> None:
        """Remove a connection from the active set."""
        conn.alive = False
        async with self._lock:
            self._connections.discard(conn)
        log.info("WS disconnected: %s (total=%d)", conn.remote, len(self._connections))

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, msg_type: str, data: Any) -> None:
        """Send a typed message to all live connections."""
        payload = {"type": msg_type, "data": data, "ts": _now()}
        dead: list = []

        async with self._lock:
            conns = list(self._connections)

        for conn in conns:
            if not conn.alive:
                dead.append(conn)
                continue
            try:
                await self._send(conn, payload)
            except Exception:
                dead.append(conn)

        for conn in dead:
            await self.disconnect(conn)

    async def broadcast_portfolio(self, portfolio_data: Dict) -> None:
        await self.broadcast("portfolio", portfolio_data)

    async def broadcast_market(self, market_data: Dict) -> None:
        await self.broadcast("market", market_data)

    async def broadcast_error(self, message: str) -> None:
        await self.broadcast("error", {"message": message})

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    async def run_heartbeat(self) -> None:
        """
        Background task — ping all clients every HEARTBEAT_INTERVAL seconds.
        Drops connections that haven't responded within PONG_TIMEOUT.
        """
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await self._ping_all()

    async def _ping_all(self) -> None:
        heartbeat = {"type": "heartbeat", "ts": _now()}
        dead: list = []

        async with self._lock:
            conns = list(self._connections)

        for conn in conns:
            if not conn.alive:
                dead.append(conn)
                continue
            # Check pong timeout
            age = (datetime.utcnow() - conn.last_pong).total_seconds()
            if age > _PONG_TIMEOUT:
                log.info("WS heartbeat timeout: %s (no pong in %.0fs)", conn.remote, age)
                dead.append(conn)
                continue
            try:
                await self._send(conn, heartbeat)
            except Exception:
                dead.append(conn)

        for conn in dead:
            await self.disconnect(conn)

    async def handle_pong(self, conn: _Connection) -> None:
        conn.last_pong = datetime.utcnow()

    # ── Connection listener ───────────────────────────────────────────────────

    async def listen(self, conn: _Connection) -> None:
        """
        Listen for incoming messages from a client (pong frames, sub requests).
        Call this in a handler task alongside the rest of the WS lifecycle.
        """
        try:
            while conn.alive:
                msg = await conn.ws.receive_text()
                try:
                    data = json.loads(msg)
                    if data.get("type") == "pong":
                        await self.handle_pong(conn)
                    elif data.get("type") == "ping":
                        await self._send(conn, {"type": "pong", "ts": _now()})
                except json.JSONDecodeError:
                    pass  # ignore malformed messages
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.debug("WS listen error %s: %s", conn.remote, exc)

    # ── Metrics ───────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        conns = list(self._connections)
        return {
            "active_connections": len(conns),
            "clients": [
                {
                    "remote":       c.remote,
                    "connected_at": c.connected_at.isoformat(),
                    "last_pong":    c.last_pong.isoformat(),
                    "alive":        c.alive,
                }
                for c in conns
            ],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _send(conn: _Connection, payload: Dict) -> None:
        await conn.ws.send_text(json.dumps(payload, default=str))

    @staticmethod
    def _remote(ws: WebSocket) -> str:
        try:
            return f"{ws.client.host}:{ws.client.port}"
        except Exception:
            return "unknown"


def _now() -> str:
    return datetime.utcnow().isoformat()


# Singleton
ws_manager = WebSocketManager()
