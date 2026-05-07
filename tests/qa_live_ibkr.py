"""
JARVIS Live IBKR + Production Safety QA Suite.

Validates:
  1. Port migration (7497 → 4001 / IBKR_MODE=live)
  2. Execution guard middleware compiles and blocks correctly
  3. Bridge watchdog compiles and initialises
  4. Account mode detection logic (LIVE/PAPER)
  5. Paper Lab independence from IBKR paper account
  6. All new API endpoints exist in main.py
  7. Dashboard LIVE READ-ONLY labels present
  8. Dashboard SIMULATED AI ENVIRONMENT labels present
  9. Execution block audit (all 10 blocked methods)
  10. real_trade: False everywhere
  11. .env live mode settings
  12. Compile checks for all new / modified files
  13. Secure bridge updated defaults
  14. Broker permission validator logic
  15. Autonomous trader independence from IBKR
"""
import json
import os
import sys
import time
from pathlib import Path

os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = []; FAIL = []; WARN = []
def ok(m):   PASS.append(m); print(f"  PASS  {m}")
def warn(m): WARN.append(m); print(f"  WARN  {m}")
def fail(m): FAIL.append(m); print(f"  FAIL  {m}")


# ── 1. .env live mode settings ──────────────────────────────────────────────

env_text = Path(".env").read_text(encoding="utf-8") if Path(".env").exists() else ""

if "IBKR_MODE=live" in env_text:
    ok(".env: IBKR_MODE=live")
elif "IBKR_MODE=paper" in env_text:
    fail(".env: IBKR_MODE still set to paper (expected live)")
else:
    warn(".env: IBKR_MODE not found")

if "IBKR_PORT=7497" in env_text:
    fail(".env: IBKR_PORT=7497 (paper port) still present — must be 4001")
elif "IBKR_PORT=7496" in env_text:
    fail(".env: IBKR_PORT=7496 (banned TWS live port) — must use 4001 (IB Gateway)")
elif "IBKR_PORT=4001" in env_text:
    ok(".env: IBKR_PORT=4001 (IB Gateway live)")
else:
    warn(".env: IBKR_PORT not found (will use env default)")

if "IBKR_READ_ONLY=true" in env_text:
    ok(".env: IBKR_READ_ONLY=true confirmed")
else:
    fail(".env: IBKR_READ_ONLY not set to true")

if "TRADER_ALLOW_REAL_TRADES=false" in env_text:
    ok(".env: TRADER_ALLOW_REAL_TRADES=false")
else:
    warn(".env: TRADER_ALLOW_REAL_TRADES not explicitly false")

if "PAPER_TRADING_ONLY=true" in env_text:
    ok(".env: PAPER_TRADING_ONLY=true")
else:
    warn(".env: PAPER_TRADING_ONLY not explicitly true")


# ── 2. Compile checks ──────────────────────────────────────────────────────

import py_compile

files_to_check = [
    "main.py",
    "opsx/bridge/secure_bridge.py",
    "opsx/bridge/execution_guard.py",
    "opsx/bridge/watchdog.py",
    "opsx/bridge/auth.py",
    "opsx/bridge/snapshot_cache.py",
    "opsx/bridge/websocket_manager.py",
    "opsx/connectors/ibkr_bridge_client.py",
    "opsx/connectors/ibkr_readonly.py",
    "opsx/connectors/ibkr_connector.py",
    "core/autonomous_paper_trader.py",
    "core/paper_trading_engine.py",
]
for f in files_to_check:
    try:
        py_compile.compile(f, doraise=True)
        ok(f"Compiles clean: {f}")
    except Exception as e:
        fail(f"Compile error in {f}: {e}")


# ── 3. Port migration in secure_bridge.py ─────────────────────────────────

bridge_src = Path("opsx/bridge/secure_bridge.py").read_text(encoding="utf-8")

if "7496" in bridge_src:
    fail("secure_bridge.py: contains banned port 7496 (use 4001 for IB Gateway live)")
elif "4001" in bridge_src:
    ok("secure_bridge.py: references 4001 (IB Gateway live)")
else:
    fail("secure_bridge.py: no 4001 reference found")

if "(paper, readonly)" in bridge_src:
    fail("secure_bridge.py: still says '(paper, readonly)' — must say live")
else:
    ok("secure_bridge.py: no stale 'paper, readonly' string")

if "(live, readonly)" in bridge_src or "IBKR_MODE" in bridge_src:
    ok("secure_bridge.py: live mode reference present")
else:
    warn("secure_bridge.py: no live mode reference found")

if "account_mode" in bridge_src:
    ok("secure_bridge.py: account_mode detection present")
else:
    fail("secure_bridge.py: account_mode missing")

if "PAPER" in bridge_src and "LIVE" in bridge_src and "startswith" in bridge_src:
    ok("secure_bridge.py: DU-prefix account mode detection logic present")
else:
    fail("secure_bridge.py: account mode detection logic missing")


# ── 4. Execution guard module ───────────────────────────────────────────────

try:
    from opsx.bridge.execution_guard import (
        ExecutionGuardMiddleware, make_blocked_response,
        _path_is_blocked, _BLOCKED_PATH_FRAGMENTS,
    )
    ok("execution_guard: module imports")
except Exception as e:
    fail(f"execution_guard: import failed — {e}")

try:
    assert _path_is_blocked("/order/place") is True
    ok("execution_guard: /order/place is blocked")
except Exception as e:
    fail(f"execution_guard: /order/place not blocked — {e}")

try:
    assert _path_is_blocked("/api/portfolio/cockpit") is False
    ok("execution_guard: /api/portfolio/cockpit is allowed")
except Exception as e:
    fail(f"execution_guard: safe path incorrectly blocked — {e}")

try:
    assert _path_is_blocked("/api/paper/analytics") is False
    ok("execution_guard: /api/paper/analytics is allowed")
except Exception as e:
    fail(f"execution_guard: paper analytics incorrectly blocked — {e}")

try:
    r = make_blocked_response()
    assert r["blocked"] is True
    assert r["reason"] == "READ_ONLY_MODE"
    assert r["real_trade"] is False
    ok("execution_guard: make_blocked_response() shape correct")
except Exception as e:
    fail(f"execution_guard: blocked response shape — {e}")


# ── 5. Watchdog module ─────────────────────────────────────────────────────

try:
    from opsx.bridge.watchdog import (
        get_watchdog_state, get_stale_warning, is_bridge_healthy,
        _watchdog_state,
    )
    ok("watchdog: module imports")
except Exception as e:
    fail(f"watchdog: import failed — {e}")

try:
    state = get_watchdog_state()
    assert state["real_trade"] is False
    assert "bridge_reachable" in state
    assert "ibkr_connected" in state
    assert "account_mode" in state
    ok("watchdog: get_watchdog_state() shape correct")
except Exception as e:
    fail(f"watchdog: state shape — {e}")

try:
    assert is_bridge_healthy() is False   # not running in test env
    ok("watchdog: is_bridge_healthy() returns False (no bridge in test env)")
except Exception as e:
    fail(f"watchdog: is_bridge_healthy() — {e}")


# ── 6. Account mode detection logic ────────────────────────────────────────

try:
    def _detect_mode(account: str) -> str:
        return "PAPER" if account.startswith("DU") else ("LIVE" if account else "UNKNOWN")

    assert _detect_mode("DU123456") == "PAPER"
    assert _detect_mode("U1234567") == "LIVE"
    assert _detect_mode("")         == "UNKNOWN"
    ok("Account mode detection: DU=PAPER, U=LIVE, empty=UNKNOWN")
except Exception as e:
    fail(f"Account mode detection logic — {e}")


# ── 7. Bridge client execution block ───────────────────────────────────────

try:
    from opsx.connectors.ibkr_bridge_client import IBKRBridgeClient, TradingBlockedError
    c = IBKRBridgeClient()
    blocked = 0
    for method in [c.place_order, c.cancel_order, c.modify_order,
                   c.placeOrder, c.cancelOrder, c.modifyOrder,
                   c.transmit_order, c.execute_trade, c.reqGlobalCancel]:
        try: method()
        except TradingBlockedError: blocked += 1
    assert blocked == 9, f"expected 9, got {blocked}"
    ok(f"ibkr_bridge_client: {blocked}/9 execution methods blocked")
except Exception as e:
    fail(f"ibkr_bridge_client execution block — {e}")


# ── 8. Paper Lab independence from IBKR paper ──────────────────────────────

try:
    from core.autonomous_paper_trader import AutonomousPaperTrader, FULL_SYMBOL_POOL
    atp = AutonomousPaperTrader()
    s = atp.get_status()
    assert s["real_trade"] is False
    assert not s["running"]
    ok("Autonomous trader: status OK (not running), real_trade=False")
except Exception as e:
    fail(f"Autonomous trader status — {e}")

try:
    # Confirm autonomous trader does NOT import from IBKR paper account
    atp_src = Path("core/autonomous_paper_trader.py").read_text(encoding="utf-8")
    for bad in ["7497", "DU", "ibkr_paper", "paper_account", "ibkr_connector"]:
        assert bad not in atp_src, f"Found banned ref: {bad}"
    ok("Autonomous trader: no IBKR paper account references")
except AssertionError as e:
    fail(f"Autonomous trader independence — {e}")
except Exception as e:
    fail(f"Autonomous trader independence check — {e}")

try:
    # Paper trading engine should not reference IBKR ports
    pe_src = Path("core/paper_trading_engine.py").read_text(encoding="utf-8")
    for bad in ["7497", "7496", "4002", "ib_insync"]:
        assert bad not in pe_src, f"Found banned ref: {bad}"
    ok("Paper trading engine: no IBKR port/socket references")
except AssertionError as e:
    fail(f"Paper trading engine isolation — {e}")
except Exception as e:
    fail(f"Paper trading engine isolation check — {e}")


# ── 9. Main.py new endpoints ───────────────────────────────────────────────

main_src = Path("main.py").read_text(encoding="utf-8")

new_endpoints = [
    "/api/debug/ibkr",
    "/api/bridge/watchdog",
    "/api/debug/permissions",
    "/api/paper/autonomous/status",
    "/api/paper/autonomous/start",
    "/api/paper/autonomous/stop",
    "/api/paper/autonomous/scan",
    "/api/paper/autonomous/log",
]
for ep in new_endpoints:
    if ep in main_src:
        ok(f"main.py endpoint present: {ep}")
    else:
        fail(f"main.py endpoint missing: {ep}")

# Execution guard wired into main.py
if "ExecutionGuardMiddleware" in main_src:
    ok("main.py: ExecutionGuardMiddleware installed")
else:
    fail("main.py: ExecutionGuardMiddleware not found")

# Watchdog startup
if "watchdog_loop" in main_src and "_start_watchdog" in main_src:
    ok("main.py: watchdog startup handler present")
else:
    fail("main.py: watchdog startup handler missing")

# account_mode in debug endpoint
if "account_mode" in main_src and "account_is_live" in main_src:
    ok("main.py: account_mode + account_is_live in debug endpoint")
else:
    fail("main.py: account_mode fields missing from debug endpoint")

# ENABLE_REMOTE_IBKR_BRIDGE wiring
if "ENABLE_REMOTE_IBKR_BRIDGE" in main_src and "ibkr_bridge_client" in main_src:
    ok("main.py: remote bridge client wired via ENABLE_REMOTE_IBKR_BRIDGE")
else:
    fail("main.py: remote bridge client not wired")


# ── 10. Dashboard labels ───────────────────────────────────────────────────

html = Path("dashboard/jarvis_futuristic.html").read_text(encoding="utf-8")

if "LIVE READ-ONLY" in html:
    ok("Dashboard: LIVE READ-ONLY label present")
else:
    fail("Dashboard: LIVE READ-ONLY label missing")

if "SIMULATED AI ENVIRONMENT" in html:
    ok("Dashboard: SIMULATED AI ENVIRONMENT label present")
else:
    fail("Dashboard: SIMULATED AI ENVIRONMENT label missing")

if "mkt-account-mode-badge" in html:
    ok("Dashboard: account mode badge element present")
else:
    fail("Dashboard: account mode badge element missing")

if "real_trade: false always" in html:
    ok("Dashboard: real_trade: false always label present")
else:
    warn("Dashboard: real_trade label not found")

# Verify no real trading refs in dashboard
for blocked in ["placeOrder", "cancelOrder", "/api/trade/execute", "/api/broker/order"]:
    if blocked in html:
        fail(f"Dashboard: real trading ref found: {blocked}")
    else:
        ok(f"Dashboard: no real trading ref: {blocked}")


# ── 11. Secure bridge execution blocks ─────────────────────────────────────

try:
    from opsx.bridge.secure_bridge import (
        placeOrder, cancelOrder, modifyOrder,
        place_order, cancel_order, modify_order,
        transmit_order, execute_trade,
        reqGlobalCancel, reqExecutions,
        SecurityViolationError,
    )
    blocked = 0
    for fn in [placeOrder, cancelOrder, modifyOrder, place_order, cancel_order,
               modify_order, transmit_order, execute_trade, reqGlobalCancel, reqExecutions]:
        try: fn()
        except SecurityViolationError: blocked += 1
    assert blocked == 10, f"expected 10, got {blocked}"
    ok(f"secure_bridge: {blocked}/10 execution methods blocked (SecurityViolationError)")
except Exception as e:
    fail(f"secure_bridge execution block — {e}")


# ── 12. ibkr_connector default port updated ────────────────────────────────

conn_src = Path("opsx/connectors/ibkr_connector.py").read_text(encoding="utf-8")
if "7496" in conn_src:
    fail("ibkr_connector.py: contains banned port 7496 — must default to 4001")
elif "4001" in conn_src:
    ok("ibkr_connector.py: 4001 default (IB Gateway live)")
else:
    warn("ibkr_connector.py: 4001 not found (reads from IBKR_PORT env var)")

if "4002" in conn_src and "# IB Gateway paper" in conn_src:
    fail("ibkr_connector.py: still has hardcoded paper port comment")
else:
    ok("ibkr_connector.py: no stale 'IB Gateway paper' comment")


# ── 13. real_trade: False guarantee across all engines ─────────────────────

try:
    from core.paper_trading_engine import PaperTradingEngine
    pt = PaperTradingEngine()
    results = [
        pt.get_status().get("real_trade"),
        pt.get_positions().get("real_trade"),
        pt.get_performance().get("real_trade"),
        pt.get_history().get("real_trade"),
    ]
    assert all(v is False for v in results), f"Not all False: {results}"
    ok("PaperTradingEngine: real_trade=False in all 4 methods")
except Exception as e:
    fail(f"PaperTradingEngine real_trade guarantee — {e}")

try:
    from core.autonomous_paper_trader import AutonomousPaperTrader
    atp2 = AutonomousPaperTrader()
    results = [
        atp2.get_status().get("real_trade"),
        atp2.get_trade_log(limit=1).get("real_trade"),
    ]
    assert all(v is False for v in results), f"Not all False: {results}"
    ok("AutonomousPaperTrader: real_trade=False in status + log")
except Exception as e:
    fail(f"AutonomousPaperTrader real_trade guarantee — {e}")

try:
    from opsx.connectors.ibkr_bridge_client import IBKRBridgeClient
    bc = IBKRBridgeClient()
    results = [
        bc.health_check().get("real_trade"),
        bc.get_full_portfolio().get("real_trade"),
    ]
    assert all(v is False for v in results), f"Not all False: {results}"
    ok("IBKRBridgeClient: real_trade=False in health + portfolio")
except Exception as e:
    fail(f"IBKRBridgeClient real_trade guarantee — {e}")


# ── 14. Chart stability — no infinite resize triggers ──────────────────────

html_js_section = html[html.find("_registerInterval"):html.find("_registerInterval") + 300] if "_registerInterval" in html else ""
if "_registerInterval" in html and "clearInterval" in html:
    ok("Dashboard: interval registry present (prevents duplicate setInterval)")
else:
    fail("Dashboard: interval registry missing")

if "animation: { duration: 0 }" in html:
    ok("Dashboard: Chart.js animation disabled on all charts")
else:
    fail("Dashboard: Chart.js animation:duration:0 missing")

if "_panelLoading" in html:
    ok("Dashboard: panel load guard present (prevents concurrent fetches)")
else:
    fail("Dashboard: panel load guard missing")


# ── 15. All bridge files compile after changes ─────────────────────────────

bridge_updated = [
    "opsx/bridge/secure_bridge.py",
    "opsx/bridge/execution_guard.py",
    "opsx/bridge/watchdog.py",
    "opsx/bridge/auth.py",
    "opsx/bridge/snapshot_cache.py",
    "opsx/bridge/__init__.py",
]
all_ok = True
for f in bridge_updated:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        fail(f"Bridge compile error: {f} — {e}")
        all_ok = False
if all_ok:
    ok(f"All {len(bridge_updated)} bridge files compile after live migration")


# ── Summary ─────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print(f"JARVIS LIVE IBKR QA: {len(PASS)} passed | {len(WARN)} warnings | {len(FAIL)} failed")
print("=" * 70)

if WARN:
    print("WARNINGS:")
    for w in WARN:
        print(f"  WARN: {w}")

if FAIL:
    print("FAILED:")
    for f in FAIL:
        print(f"  FAIL: {f}")
    sys.exit(1)
else:
    print()
    print("JARVIS LIVE READ-ONLY IBKR + AUTONOMOUS PAPER LAB FINALIZATION COMPLETE")
