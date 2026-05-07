"""
JARVIS Secure IBKR Local Bridge — v1.1  (event-loop-safe).

Architecture (after event-loop fix):
  ┌─────────────────────────────────────────────────────────────┐
  │  FastAPI / uvicorn event loop                               │
  │    broadcast_from_cache()  ─── reads snapshot_cache ──►WS  │
  │    market_snapshot_task()  ─── yfinance, run_in_executor    │
  │    ws_manager.run_heartbeat()                               │
  │    HTTP endpoints          ─── read-only from snapshot_cache│
  └──────────────────┬──────────────────────────────────────────┘
                     │ snapshot_cache (thread-safe RLock)
  ┌──────────────────▼──────────────────────────────────────────┐
  │  IBKRWorkerThread  (daemon OS thread)                       │
  │    asyncio.new_event_loop() → asyncio.set_event_loop()      │
  │    ib_insync IB().connect(localhost:4002, readonly=True)     │
  │    Poll loop: connect → _poll() → ib.sleep(30s) → repeat    │
  │    Writes to snapshot_cache on every successful poll        │
  └─────────────────────────────────────────────────────────────┘

Root cause of original crash:
  run_in_executor(None, _connect_ibkr) places ib_insync into a
  ThreadPoolExecutor thread that has no asyncio event loop.
  Python 3.10+ no longer auto-creates a loop on get_event_loop()
  in non-main threads → RuntimeError: no current event loop.

Fix: IBKRWorkerThread creates asyncio.new_event_loop() itself
  and calls asyncio.set_event_loop() before any ib_insync call.
  FastAPI never calls ib_insync. Full isolation.

Security model:
  - Token auth on every HTTP route (Bearer token via auth.py)
  - IBKR connected to localhost ONLY — never routed to internet
  - ALL execution methods HARD BLOCKED at module level
  - Stale snapshot returned if IBKR disconnects (never silent failure)
  - real_trade: False in every response

Run locally:
  python -m opsx.bridge.secure_bridge
  -- or --
  uvicorn opsx.bridge.secure_bridge:app --host 0.0.0.0 --port 7755

Environment variables:
  BRIDGE_PORT           default 7755
  BRIDGE_HOST           default 0.0.0.0
  BRIDGE_API_TOKEN      if set, used as auth token; else auto-generated
  BRIDGE_POLL_INTERVAL  default 30s  (IBKR data refresh interval)
  BRIDGE_MARKET_INTERVAL default 120s (market snapshot refresh)
  IBKR_HOST             default 127.0.0.1
  IBKR_PORT             default 4002
  IBKR_CLIENT_ID        default 10  (avoids clash with main app client 1)

CRITICAL: This module NEVER imports placeOrder, cancelOrder, modifyOrder,
          reqGlobalCancel, or any execution-related IBKR methods.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from opsx.bridge.auth import verify_token, get_bridge_token
from opsx.bridge.snapshot_cache import snapshot_cache
from opsx.bridge.websocket_manager import ws_manager

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

log = logging.getLogger("jarvis.bridge")

# ── Config ────────────────────────────────────────────────────────────────────
BRIDGE_HOST      = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT      = int(os.getenv("BRIDGE_PORT", "7755"))
POLL_INTERVAL    = int(os.getenv("BRIDGE_POLL_INTERVAL", "30"))
MARKET_INTERVAL  = int(os.getenv("BRIDGE_MARKET_INTERVAL", "120"))
RECONNECT_WAIT   = 60   # seconds to wait between failed connect attempts
MARKET_SYMBOLS   = ["SPY", "QQQ", "IWM", "DXY", "GLD", "TLT"]

# ── Module-level worker handle ────────────────────────────────────────────────
_worker_thread: Optional["IBKRWorkerThread"] = None


# ── Execution method HARD BLOCK ───────────────────────────────────────────────
# Defined at module level — no ib_insync execution methods are imported anywhere.

class SecurityViolationError(Exception):
    """Raised if any execution path is attempted on the bridge."""


def _block_execution(method: str) -> None:
    _write_guardrail(method)
    raise SecurityViolationError(
        f"BLOCKED: '{method}' is forbidden on the JARVIS Secure Bridge. "
        "This is a READ-ONLY connection."
    )


def _write_guardrail(method: str) -> None:
    try:
        path = Path("data/bridge/guardrail_log.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        entries: list = []
        if path.exists():
            entries = json.loads(path.read_text(encoding="utf-8"))
        entries.append({
            "timestamp": datetime.utcnow().isoformat(),
            "method":    method,
            "blocked":   True,
            "source":    "secure_bridge",
        })
        path.write_text(json.dumps(entries[-500:], indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    log.critical("BRIDGE SECURITY VIOLATION BLOCKED — method=%s", method)


placeOrder      = lambda *a, **k: _block_execution("placeOrder")       # noqa: E731
cancelOrder     = lambda *a, **k: _block_execution("cancelOrder")      # noqa: E731
modifyOrder     = lambda *a, **k: _block_execution("modifyOrder")      # noqa: E731
place_order     = lambda *a, **k: _block_execution("place_order")      # noqa: E731
cancel_order    = lambda *a, **k: _block_execution("cancel_order")     # noqa: E731
modify_order    = lambda *a, **k: _block_execution("modify_order")     # noqa: E731
transmit_order  = lambda *a, **k: _block_execution("transmit_order")   # noqa: E731
execute_trade   = lambda *a, **k: _block_execution("execute_trade")    # noqa: E731
reqGlobalCancel = lambda *a, **k: _block_execution("reqGlobalCancel")  # noqa: E731
reqExecutions   = lambda *a, **k: _block_execution("reqExecutions")    # noqa: E731


# ── IBKRWorkerThread ──────────────────────────────────────────────────────────

class IBKRWorkerThread(threading.Thread):
    """
    Owns the entire ib_insync lifecycle in an isolated OS thread.

    Thread startup creates its own asyncio event loop via
        asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    so ib_insync never sees the uvicorn/FastAPI event loop.

    Writes portfolio snapshots to snapshot_cache on every poll cycle.
    FastAPI never calls ib_insync — it only reads from snapshot_cache.

    Reconnect behaviour:
      - On connect failure: waits RECONNECT_WAIT seconds, retries
      - On poll/sleep failure: drops IB object, triggers reconnect next iteration
      - On IB Gateway restart: ib.isConnected() becomes False → immediate reconnect
    """

    def __init__(self) -> None:
        super().__init__(daemon=True, name="ibkr-worker")
        self._lock          = threading.Lock()
        self._connected_val = False
        self._account_val   = ""
        self._stop_event    = threading.Event()

    # ── Thread-safe properties ────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected_val

    @property
    def account(self) -> str:
        with self._lock:
            return self._account_val

    def _set_state(self, connected: bool, account: str = "") -> None:
        with self._lock:
            self._connected_val = connected
            self._account_val   = account

    def stop(self) -> None:
        """Signal the worker to exit cleanly after the current sleep."""
        self._stop_event.set()

    # ── Main thread loop ──────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Thread entry point.

        Creates an isolated event loop for this thread so ib_insync
        never touches the uvicorn event loop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        log.info("IBKR worker thread started (own event loop: %s)", id(loop))

        ib = None

        while not self._stop_event.is_set():
            # ── (Re)connect if needed ─────────────────────────────────────
            if ib is None or not ib.isConnected():
                self._set_state(False)
                ib = self._try_connect()
                if ib is None:
                    # Wait before next attempt — check stop_event so shutdown is fast
                    log.info("IBKR worker waiting %ds before reconnect", RECONNECT_WAIT)
                    self._stop_event.wait(RECONNECT_WAIT)
                    continue

            # ── Poll data ─────────────────────────────────────────────────
            data = self._poll(ib)
            if data:
                snapshot_cache.set("portfolio", data)
                log.debug(
                    "IBKR worker snapshot saved: %d positions net_liq=%.2f",
                    data.get("position_count", 0),
                    data.get("net_liquidation", 0),
                )
            else:
                # poll returned None → connection lost mid-poll
                self._set_state(False)
                ib = None
                continue

            # ── ib.sleep() — processes TWS messages for POLL_INTERVAL s ──
            # This is the ib_insync message pump; it must run in THIS thread.
            # It will raise if the connection drops during the sleep.
            try:
                ib.sleep(POLL_INTERVAL)
            except Exception as exc:
                log.warning("IBKR worker sleep interrupted: %s", exc)
                self._set_state(False)
                ib = None

        # ── Clean shutdown ────────────────────────────────────────────────
        if ib is not None:
            try:
                ib.disconnect()
            except Exception:
                pass
        log.info("IBKR worker thread stopped")

    # ── Connect helper ────────────────────────────────────────────────────────

    def _try_connect(self) -> Optional[Any]:
        """
        Attempt ib_insync connection.
        Safe to call from this thread — asyncio.set_event_loop() was called in run().
        """
        ibkr_host = os.getenv("IBKR_HOST", "127.0.0.1")
        ibkr_port = int(os.getenv("IBKR_PORT", "4002"))
        client_id = int(os.getenv("IBKR_CLIENT_ID", "10"))

        try:
            from ib_insync import IB, util
            util.logToConsole(logging.WARNING)

            ib = IB()
            ib.connect(
                ibkr_host,
                ibkr_port,
                clientId=client_id,
                readonly=True,
                timeout=10,
            )
            accounts = ib.managedAccounts()
            account  = accounts[0] if accounts else ""
            self._set_state(True, account)
            log.info(
                "IBKR worker connected: %s:%d account=%s clientId=%d",
                ibkr_host, ibkr_port, account, client_id,
            )
            return ib

        except Exception as exc:
            log.warning("IBKR worker connect failed: %s", exc)
            return None

    # ── Poll helper ───────────────────────────────────────────────────────────

    def _poll(self, ib: Any) -> Optional[Dict]:
        """
        Fetch account summary + positions + P&L.
        All ib_insync calls happen in this thread — safe.
        Returns None on any error (triggers reconnect in run()).
        """
        account = self.account
        if not account:
            accounts = ib.managedAccounts()
            account  = accounts[0] if accounts else ""
            if account:
                self._set_state(True, account)

        try:
            # Account summary ─────────────────────────────────────────────
            summary_items = ib.accountSummary(account)
            summary: Dict[str, Any] = {}
            for item in summary_items:
                if item.tag in (
                    "NetLiquidation", "TotalCashValue", "UnrealizedPnL",
                    "RealizedPnL", "GrossPositionValue", "BuyingPower",
                    "AvailableFunds", "Currency",
                ):
                    try:
                        summary[item.tag] = float(item.value)
                    except (TypeError, ValueError):
                        summary[item.tag] = item.value

            # Positions ───────────────────────────────────────────────────
            raw_positions = ib.positions(account)
            positions: List[Dict] = []
            for pos in raw_positions:
                contract = pos.contract
                qty      = float(pos.position or 0)
                avg_cost = float(pos.avgCost or 0)
                mkt_val  = round(avg_cost * qty, 2)
                positions.append({
                    "symbol":         contract.symbol,
                    "sec_type":       contract.secType,
                    "quantity":       qty,
                    "avg_cost":       round(avg_cost, 4),
                    "market_value":   mkt_val,
                    "unrealized_pnl": 0.0,
                    "currency":       contract.currency,
                    "real_trade":     False,
                })

            # P&L — subscribe, brief pump, unsubscribe ────────────────────
            pnl_obj    = ib.reqPnL(account)
            ib.sleep(0.5)                   # pump: let PnL data arrive
            daily_pnl  = float(getattr(pnl_obj, "dailyPnL",     0) or 0)
            unrealized = float(getattr(pnl_obj, "unrealizedPnL", 0) or 0)
            realized   = float(getattr(pnl_obj, "realizedPnL",   0) or 0)
            try:
                ib.cancelPnL(account)
            except Exception:
                pass

            return {
                "status":          "ok",
                "account":         account,
                "net_liquidation": summary.get("NetLiquidation", 0),
                "total_cash":      summary.get("TotalCashValue", 0),
                "gross_position":  summary.get("GrossPositionValue", 0),
                "buying_power":    summary.get("BuyingPower", 0),
                "available_funds": summary.get("AvailableFunds", 0),
                "unrealized_pnl":  round(unrealized, 2),
                "realized_pnl":    round(realized, 2),
                "daily_pnl":       round(daily_pnl, 2),
                "positions":       positions,
                "position_count":  len(positions),
                "real_trade":      False,
                "fetched_at":      datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            log.error("IBKR worker poll failed: %s", exc)
            self._set_state(False)
            return None


# ── Market snapshot (pure yfinance — safe in executor) ────────────────────────

def _fetch_market_snapshot() -> Dict:
    """Fetch index prices via yfinance. No ib_insync — safe for run_in_executor."""
    try:
        import yfinance as yf
        items: List[Dict] = []
        for sym in MARKET_SYMBOLS:
            try:
                h = yf.Ticker(sym).history(period="2d", interval="1d")
                if h.empty:
                    continue
                close = float(h["Close"].iloc[-1])
                prev  = float(h["Close"].iloc[-2]) if len(h) >= 2 else close
                chg   = round((close - prev) / prev * 100, 2) if prev else 0
                items.append({
                    "symbol":     sym,
                    "price":      round(close, 2),
                    "change_pct": chg,
                    "direction":  "up" if chg > 0 else ("down" if chg < 0 else "flat"),
                })
            except Exception:
                pass
        return {"items": items, "generated_at": datetime.utcnow().isoformat()}
    except Exception as exc:
        return {"items": [], "error": str(exc), "generated_at": datetime.utcnow().isoformat()}


# ── FastAPI background tasks (uvicorn loop — NO ib_insync) ────────────────────

async def broadcast_from_cache() -> None:
    """
    Reads portfolio from snapshot_cache (written by IBKRWorkerThread)
    and pushes to all connected WebSocket clients.

    Runs entirely in the FastAPI event loop — never touches ib_insync.
    """
    await asyncio.sleep(8)   # initial delay — let worker thread connect first
    _last_fetched_at: Optional[str] = None

    while True:
        try:
            data, is_stale = snapshot_cache.get("portfolio")
            connected = _worker_thread.connected if _worker_thread else False

            if data:
                fetched_at = data.get("fetched_at")
                if fetched_at != _last_fetched_at:
                    _last_fetched_at = fetched_at
                    await ws_manager.broadcast_portfolio(data)
            elif not connected:
                stale = snapshot_cache.get_fresh_or_stale("portfolio")
                await ws_manager.broadcast("disconnected", {
                    "status":   "ibkr_disconnected",
                    "message":  "IB Gateway not reachable — serving cached data",
                    "snapshot": stale,
                    "real_trade": False,
                })

        except Exception as exc:
            log.error("Broadcast task: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)


async def market_snapshot_task() -> None:
    """
    Refreshes market index prices via yfinance in a thread executor.
    Safe: yfinance has no event-loop dependency.
    """
    loop = asyncio.get_event_loop()

    async def _refresh() -> None:
        snap = await loop.run_in_executor(None, _fetch_market_snapshot)
        if snap.get("items"):
            snapshot_cache.set("market", snap)
            await ws_manager.broadcast_market(snap)

    await _refresh()          # initial load on startup
    while True:
        await asyncio.sleep(MARKET_INTERVAL)
        try:
            await _refresh()
        except Exception as exc:
            log.error("Market snapshot task: %s", exc)


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_thread

    log.info("JARVIS Secure Bridge starting on port %d", BRIDGE_PORT)
    get_bridge_token()   # ensure token is generated before first request

    # Start the IBKR worker thread (owns ib_insync, has its own event loop)
    # Never touch ib_insync from the FastAPI event loop after this point.
    _worker_thread = IBKRWorkerThread()
    _worker_thread.start()
    log.info("IBKR worker thread started: %s", _worker_thread.name)

    # Start async background tasks in the FastAPI event loop
    asyncio.create_task(broadcast_from_cache(),       name="bridge-broadcast")
    asyncio.create_task(market_snapshot_task(),       name="bridge-market")
    asyncio.create_task(ws_manager.run_heartbeat(),   name="bridge-heartbeat")

    log.info("Bridge ready — token: data/bridge/bridge_token.key")
    yield

    # Shutdown — signal worker to stop and wait up to 10s
    log.info("Bridge shutting down…")
    if _worker_thread:
        _worker_thread.stop()
        _worker_thread.join(timeout=10)

    log.info("Bridge shutdown complete")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS Secure IBKR Bridge",
    description=(
        "Local read-only bridge: Railway JARVIS → IB Gateway (paper). "
        "Token-authenticated. No execution endpoints."
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "X-Bridge-Token", "Content-Type"],
)


@app.exception_handler(SecurityViolationError)
async def security_violation_handler(request, exc):
    return JSONResponse(
        status_code=403,
        content={"error": "SecurityViolation", "message": str(exc), "real_trade": False},
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health(_token: str = Depends(verify_token)):
    """Bridge health, IBKR connection state, cache stats, WS connections."""
    connected = _worker_thread.connected if _worker_thread else False
    account   = _worker_thread.account   if _worker_thread else ""
    _, is_stale = snapshot_cache.get("portfolio")

    return {
        "status":         "ok",
        "bridge_version": "1.1.0",
        "ibkr": {
            "connected":  connected,
            "account":    account,
            "host":       os.getenv("IBKR_HOST", "127.0.0.1"),
            "port":       int(os.getenv("IBKR_PORT", "4002")),
            "client_id":  int(os.getenv("IBKR_CLIENT_ID", "10")),
            "readonly":   True,
        },
        "cache": {
            "portfolio_stale": is_stale,
            **snapshot_cache.stats(),
        },
        "websocket":       ws_manager.stats(),
        "worker_thread":   _worker_thread.name if _worker_thread else None,
        "poll_interval":   POLL_INTERVAL,
        "execution_blocked": True,
        "real_trade":      False,
        "generated_at":    datetime.utcnow().isoformat(),
    }


# ── Portfolio endpoints — all read from snapshot_cache ───────────────────────
# The worker thread keeps the cache fresh. Endpoints never call ib_insync.

@app.get("/portfolio/summary")
async def portfolio_summary(_token: str = Depends(verify_token)):
    """Account-level financial summary. Stale-flagged when IBKR disconnected."""
    connected = _worker_thread.connected if _worker_thread else False
    cached, is_stale = snapshot_cache.get("portfolio")

    if cached:
        return {
            "status":          "stale" if is_stale else "ok",
            "account":         cached.get("account", ""),
            "net_liquidation": cached.get("net_liquidation", 0),
            "total_cash":      cached.get("total_cash", 0),
            "gross_position":  cached.get("gross_position", 0),
            "buying_power":    cached.get("buying_power", 0),
            "available_funds": cached.get("available_funds", 0),
            "unrealized_pnl":  cached.get("unrealized_pnl", 0),
            "realized_pnl":    cached.get("realized_pnl", 0),
            "daily_pnl":       cached.get("daily_pnl", 0),
            "position_count":  cached.get("position_count", 0),
            "_stale":          is_stale,
            "_stale_age_sec":  cached.get("_stale_age_sec"),
            "_stale_reason":   ("IBKR disconnected — cached data" if not connected else None),
            "real_trade":      False,
            "fetched_at":      cached.get("fetched_at"),
        }

    return {
        "status":    "no_data",
        "message":   "IBKR not connected and no cached snapshot available",
        "_stale":    True,
        "real_trade": False,
    }


@app.get("/portfolio/positions")
async def portfolio_positions(_token: str = Depends(verify_token)):
    """All open positions. Stale-flagged on IBKR disconnect."""
    connected = _worker_thread.connected if _worker_thread else False
    cached, is_stale = snapshot_cache.get("portfolio")

    if cached:
        return {
            "status":    "stale" if is_stale else "ok",
            "positions": cached.get("positions", []),
            "count":     len(cached.get("positions", [])),
            "_stale":    is_stale,
            "_stale_reason": (None if connected else "IBKR disconnected — cached positions"),
            "real_trade": False,
            "fetched_at": cached.get("fetched_at"),
        }

    return {"status": "no_data", "positions": [], "count": 0, "_stale": True, "real_trade": False}


@app.get("/portfolio/pnl")
async def portfolio_pnl(_token: str = Depends(verify_token)):
    """Daily + unrealized + realized P&L."""
    connected = _worker_thread.connected if _worker_thread else False
    cached, is_stale = snapshot_cache.get("portfolio")

    if cached:
        return {
            "status":         "stale" if is_stale else "ok",
            "daily_pnl":      cached.get("daily_pnl", 0),
            "unrealized_pnl": cached.get("unrealized_pnl", 0),
            "realized_pnl":   cached.get("realized_pnl", 0),
            "_stale":         is_stale,
            "_stale_reason":  (None if connected else "IBKR disconnected"),
            "real_trade":     False,
            "fetched_at":     cached.get("fetched_at"),
        }

    return {
        "status":         "no_data",
        "daily_pnl":      0,
        "unrealized_pnl": 0,
        "realized_pnl":   0,
        "_stale":         True,
        "real_trade":     False,
    }


@app.get("/portfolio/risk")
async def portfolio_risk(_token: str = Depends(verify_token)):
    """Risk analysis via JARVIS PortfolioIntelligenceEngine (read-only)."""
    try:
        from core.portfolio_intelligence_engine import PortfolioIntelligenceEngine
        pie = PortfolioIntelligenceEngine()
        raw, _ = snapshot_cache.get("portfolio")
        analysis = pie.analyze(_to_unified_format(raw)) if raw else pie._no_data_report()
        analysis["real_trade"] = False
        return analysis
    except Exception as exc:
        log.error("portfolio_risk: %s", exc)
        return {"status": "error", "error": str(exc), "real_trade": False}


# ── Market snapshot ────────────────────────────────────────────────────────────

@app.get("/market/snapshot")
async def market_snapshot(_token: str = Depends(verify_token)):
    """Index prices (SPY/QQQ/IWM/GLD/TLT/DXY) — refreshed every MARKET_INTERVAL s."""
    cached, is_stale = snapshot_cache.get("market")
    if cached and not is_stale:
        return {**cached, "real_trade": False}

    # On-demand refresh (yfinance, runs in executor — no event loop dependency)
    loop = asyncio.get_event_loop()
    try:
        fresh = await loop.run_in_executor(None, _fetch_market_snapshot)
        if fresh.get("items"):
            snapshot_cache.set("market", fresh)
            return {**fresh, "_stale": False, "real_trade": False}
    except Exception as exc:
        log.error("market_snapshot on-demand: %s", exc)

    if cached:
        return {**cached, "_stale": True, "real_trade": False}
    return {"items": [], "status": "no_data", "_stale": True, "real_trade": False}


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Real-time push: portfolio + market + heartbeat.
    Authenticate via query param: /ws?token=<bridge_token>
    """
    token = ws.query_params.get("token", "")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    from opsx.bridge.auth import verify_token_value
    if not verify_token_value(token):
        await ws.close(code=4001, reason="Invalid token")
        return

    conn = await ws_manager.connect(ws)

    # Push current snapshots immediately on connect
    snap, _   = snapshot_cache.get("portfolio")
    market, _ = snapshot_cache.get("market")
    if snap:
        await ws_manager.broadcast_portfolio(snap)
    if market:
        await ws_manager.broadcast_market(market)

    try:
        await ws_manager.listen(conn)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(conn)


# ── Bridge info ────────────────────────────────────────────────────────────────

@app.get("/bridge/info")
async def bridge_info(_token: str = Depends(verify_token)):
    """Bridge config — token prefix, blocked methods, connection config."""
    token = get_bridge_token()
    return {
        "bridge_version":    "1.1.0",
        "token_prefix":      token[:8] + "…",
        "ibkr_host":         os.getenv("IBKR_HOST", "127.0.0.1"),
        "ibkr_port":         int(os.getenv("IBKR_PORT", "4002")),
        "ibkr_client_id":    int(os.getenv("IBKR_CLIENT_ID", "10")),
        "poll_interval_sec": POLL_INTERVAL,
        "execution_blocked": True,
        "real_trade":        False,
        "blocked_methods": [
            "placeOrder", "cancelOrder", "modifyOrder", "place_order",
            "cancel_order", "modify_order", "transmit_order", "execute_trade",
            "reqGlobalCancel", "reqExecutions",
        ],
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_unified_format(bridge_snapshot: Dict) -> Dict:
    """Convert bridge portfolio snapshot → UnifiedPortfolioEngine format."""
    positions = bridge_snapshot.get("positions", [])
    total_val = bridge_snapshot.get("gross_position", 0) or sum(
        p.get("market_value", 0) for p in positions
    )
    return {
        "status":                "ok" if positions else "no_data",
        "all_positions":         positions,
        "total_market_value":    total_val,
        "total_cash":            bridge_snapshot.get("total_cash", 0),
        "total_daily_pnl":       bridge_snapshot.get("daily_pnl", 0),
        "total_unrealized_pnl":  bridge_snapshot.get("unrealized_pnl", 0),
        "sector_exposure":       [],
        "theme_exposure":        [],
        "asset_class_exposure":  [],
        "concentration_warnings": [],
        "brokers": {
            "ibkr": {
                "status":       "ok",
                "market_value": total_val,
                "_stale":       bridge_snapshot.get("_stale", False),
            }
        },
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    print(f"\nJARVIS Secure Bridge v1.1 — event-loop-safe")
    print(f"Listening: {BRIDGE_HOST}:{BRIDGE_PORT}")
    print(f"IBKR target: {os.getenv('IBKR_HOST','127.0.0.1')}:{os.getenv('IBKR_PORT','4002')} (paper, readonly)")
    print(f"Token: data/bridge/bridge_token.key")
    print(f"All execution methods: HARD BLOCKED\n")

    uvicorn.run(
        "opsx.bridge.secure_bridge:app",
        host=BRIDGE_HOST,
        port=BRIDGE_PORT,
        reload=False,
        log_level="info",
    )
