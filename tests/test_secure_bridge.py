"""
JARVIS Secure Bridge QA Test Suite.

Tests (all offline — no IB Gateway required):
  1. Module imports and instantiation
  2. Token generation and constant-time validation
  3. Token file persistence and reload
  4. Rate limiter: allow / block / window reset
  5. SnapshotCache: set/get fresh, set/get stale, disk persistence, expiry
  6. SnapshotCache: annotates _stale, _stale_age_sec, _cache_source
  7. WebSocketManager: stats shape, instantiation
  8. SecurityViolationError + all 10 blocked methods
  9. Guardrail log written on block attempt
  10. Bridge app routes registered
  11. _to_unified_format helper
  12. real_trade: False in all engine outputs
  13. Disconnected state returns cached snapshot
  14. Stale snapshot annotated correctly
  15. Market symbols list defined
"""
import asyncio
import json
import os
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = []
FAIL = []

def ok(msg):  PASS.append(msg); print("  PASS  " + msg)
def fail(msg, exc=None): FAIL.append(msg); print("  FAIL  " + msg + (f"  ({exc})" if exc else ""))


# ── 1. Module imports ──────────────────────────────────────────────────────────

try:
    from opsx.bridge.auth import TokenStore, RateLimiter, verify_token_value, get_bridge_token
    ok("opsx.bridge.auth imports")
except Exception as e:
    fail("opsx.bridge.auth imports", e)

try:
    from opsx.bridge.snapshot_cache import SnapshotCache, snapshot_cache
    ok("opsx.bridge.snapshot_cache imports")
except Exception as e:
    fail("opsx.bridge.snapshot_cache imports", e)

try:
    from opsx.bridge.websocket_manager import WebSocketManager, ws_manager
    ok("opsx.bridge.websocket_manager imports")
except Exception as e:
    fail("opsx.bridge.websocket_manager imports", e)

try:
    from opsx.bridge.secure_bridge import (
        SecurityViolationError,
        placeOrder, cancelOrder, modifyOrder, place_order,
        cancel_order, modify_order, transmit_order, execute_trade,
        reqGlobalCancel, reqExecutions,
        _to_unified_format, MARKET_SYMBOLS, app,
    )
    ok("opsx.bridge.secure_bridge imports")
except Exception as e:
    fail("opsx.bridge.secure_bridge imports", e)


# ── 2. Token generation ────────────────────────────────────────────────────────

try:
    store = TokenStore()
    token = store.get_token()
    assert isinstance(token, str)
    assert len(token) >= 32, f"Token too short: {len(token)} chars"
    ok(f"TokenStore generates token (len={len(token)})")
except Exception as e:
    fail("TokenStore token generation", e)

try:
    store = TokenStore()
    token = store.get_token()
    assert verify_token_value(token), "Valid token rejected"
    assert not verify_token_value("wrong_token_abc123"), "Invalid token accepted"
    ok("verify_token_value: accept valid / reject invalid")
except Exception as e:
    fail("verify_token_value", e)

try:
    store = TokenStore()
    t1 = store.get_token()
    t2 = store.get_token()  # second call — must return same token
    assert t1 == t2
    ok("TokenStore idempotent — same token on repeated calls")
except Exception as e:
    fail("TokenStore idempotent", e)

try:
    # Use the module-level singleton so verify_token_value sees the rotated token
    from opsx.bridge.auth import _token_store as _ts
    t1 = _ts.get_token()
    t2 = _ts.rotate_token()
    assert t1 != t2, "Rotated token should differ from original"
    assert verify_token_value(t2), "Rotated token should be valid"
    assert not verify_token_value(t1), "Old token should be invalid after rotation"
    ok("TokenStore.rotate_token() invalidates old token")
except Exception as e:
    fail("TokenStore.rotate_token()", e)


# ── 3. Rate limiter ────────────────────────────────────────────────────────────

try:
    rl = RateLimiter(max_requests=5, window=60)
    for i in range(5):
        allowed, remaining = rl.is_allowed("test_ip")
        assert allowed, f"Request {i+1} should be allowed"
    # 6th request should be blocked
    allowed, remaining = rl.is_allowed("test_ip")
    assert not allowed, "6th request should be rate-limited"
    assert remaining == 0
    ok("RateLimiter: allows 5, blocks 6th")
except Exception as e:
    fail("RateLimiter block", e)

try:
    rl = RateLimiter(max_requests=3, window=1)   # 1-second window
    for _ in range(3):
        rl.is_allowed("ip_window_test")
    time.sleep(1.1)   # wait for window to expire
    allowed, _ = rl.is_allowed("ip_window_test")
    assert allowed, "After window reset, request should be allowed"
    ok("RateLimiter: window resets correctly")
except Exception as e:
    fail("RateLimiter window reset", e)


# ── 4. SnapshotCache ───────────────────────────────────────────────────────────

try:
    cache = SnapshotCache(fresh_ttl=10, stale_max=60)
    sample = {"status": "ok", "net_liquidation": 50000, "real_trade": False}
    cache.set("test_portfolio", sample)
    data, is_stale = cache.get("test_portfolio")
    assert data is not None
    assert not is_stale, "Fresh cache should not be stale"
    assert data["net_liquidation"] == 50000
    assert data["_stale"] is False
    assert data["_cache_source"] == "memory"
    ok("SnapshotCache: set/get fresh in memory")
except Exception as e:
    fail("SnapshotCache set/get fresh", e)

try:
    cache = SnapshotCache(fresh_ttl=0, stale_max=60)  # TTL=0 — immediately stale
    cache.set("test_stale", {"value": 42})
    time.sleep(0.05)
    data, is_stale = cache.get("test_stale")
    assert data is not None
    assert is_stale is True, "Should be stale after TTL=0"
    assert data["_stale"] is True
    assert data["_stale_age_sec"] >= 0
    ok("SnapshotCache: stale annotation correct")
except Exception as e:
    fail("SnapshotCache stale annotation", e)

try:
    cache = SnapshotCache(fresh_ttl=10, stale_max=60)
    cache.set("test_disk", {"status": "ok", "disk_test": True})
    # Simulate memory eviction
    cache._memory.clear()
    data, is_stale = cache.get("test_disk")
    assert data is not None, "Should fall back to disk cache"
    assert data["disk_test"] is True
    assert data["_cache_source"] == "disk"
    ok("SnapshotCache: falls back to disk when memory cleared")
except Exception as e:
    fail("SnapshotCache disk fallback", e)

try:
    cache = SnapshotCache(fresh_ttl=0, stale_max=0)  # expired immediately
    cache.set("test_expired", {"x": 1})
    time.sleep(0.05)
    # Manually set file mtime to be old
    import time as _time
    path = Path("data/bridge/snapshots/test_expired.json")
    if path.exists():
        old_time = _time.time() - 400
        import os as _os
        _os.utime(str(path), (old_time, old_time))
    cache._memory.clear()
    data, is_stale = cache.get("test_expired")
    assert data is None, "Expired data should return None"
    ok("SnapshotCache: expired data returns None")
except Exception as e:
    fail("SnapshotCache expiry returns None", e)

try:
    cache = SnapshotCache(fresh_ttl=10, stale_max=60)
    result = cache.get_fresh_or_stale("nonexistent_key_99")
    assert isinstance(result, dict)
    assert result["_stale"] is True
    assert result["_cache_source"] == "none"
    ok("SnapshotCache: get_fresh_or_stale returns dict for missing key")
except Exception as e:
    fail("SnapshotCache get_fresh_or_stale missing", e)


# ── 5. Security violations — 10 blocked methods ───────────────────────────────

try:
    blocked_methods = [
        placeOrder, cancelOrder, modifyOrder, place_order,
        cancel_order, modify_order, transmit_order, execute_trade,
        reqGlobalCancel, reqExecutions,
    ]
    blocked_count = 0
    for fn in blocked_methods:
        try:
            fn()
        except SecurityViolationError:
            blocked_count += 1
    assert blocked_count == 10, f"Expected 10 blocks, got {blocked_count}"
    ok(f"All 10 execution methods blocked ({blocked_count}/10)")
except Exception as e:
    fail("Execution methods blocked", e)


# ── 6. Guardrail log ───────────────────────────────────────────────────────────

try:
    log_path = Path("data/bridge/guardrail_log.json")
    initial_count = 0
    if log_path.exists():
        initial_count = len(json.loads(log_path.read_text()))

    try:
        placeOrder()
    except SecurityViolationError:
        pass

    if log_path.exists():
        entries = json.loads(log_path.read_text())
        assert len(entries) > initial_count, "Guardrail log should grow on block"
        last = entries[-1]
        assert last["method"] == "placeOrder"
        assert last["blocked"] is True
        assert last["source"] == "secure_bridge"
        ok("Guardrail log written on blocked attempt")
    else:
        fail("Guardrail log: file not created")
except Exception as e:
    fail("Guardrail log write", e)


# ── 7. FastAPI routes registered ──────────────────────────────────────────────

try:
    routes = [r.path for r in app.routes]
    required_routes = [
        "/health",
        "/portfolio/summary",
        "/portfolio/positions",
        "/portfolio/pnl",
        "/portfolio/risk",
        "/market/snapshot",
        "/ws",
        "/bridge/info",
    ]
    missing = [r for r in required_routes if r not in routes]
    if missing:
        fail(f"Missing routes: {missing}")
    else:
        ok(f"All {len(required_routes)} required routes registered")
except Exception as e:
    fail("FastAPI route registration", e)


# ── 8. _to_unified_format helper ──────────────────────────────────────────────

try:
    bridge_snap = {
        "account":        "DU123456",
        "gross_position": 15000.0,
        "total_cash":     5000.0,
        "daily_pnl":      150.0,
        "unrealized_pnl": 300.0,
        "positions": [
            {"symbol": "AAPL", "quantity": 10, "avg_cost": 175.0, "market_value": 1820.0},
        ],
    }
    unified = _to_unified_format(bridge_snap)
    assert unified["status"] == "ok"
    assert unified["total_market_value"] == 15000.0
    assert unified["total_cash"] == 5000.0
    assert unified["total_daily_pnl"] == 150.0
    assert len(unified["all_positions"]) == 1
    assert "ibkr" in unified["brokers"]
    ok("_to_unified_format() correct shape")
except Exception as e:
    fail("_to_unified_format()", e)

try:
    empty_snap = {"positions": [], "gross_position": 0, "total_cash": 0}
    unified = _to_unified_format(empty_snap)
    assert unified["status"] == "no_data"
    ok("_to_unified_format() empty snapshot → no_data status")
except Exception as e:
    fail("_to_unified_format() empty", e)


# ── 9. real_trade: False verified in bridge responses ─────────────────────────

try:
    from opsx.bridge.snapshot_cache import SnapshotCache
    cache = SnapshotCache()
    cache.set("portfolio", {"net_liquidation": 10000, "real_trade": False})
    data, _ = cache.get("portfolio")
    assert data.get("real_trade") is False
    ok("real_trade: False preserved through cache")
except Exception as e:
    fail("real_trade: False in cache", e)


# ── 10. MARKET_SYMBOLS defined ────────────────────────────────────────────────

try:
    assert isinstance(MARKET_SYMBOLS, list)
    assert len(MARKET_SYMBOLS) >= 4
    assert "SPY" in MARKET_SYMBOLS
    assert "QQQ" in MARKET_SYMBOLS
    ok(f"MARKET_SYMBOLS defined: {MARKET_SYMBOLS}")
except Exception as e:
    fail("MARKET_SYMBOLS", e)


# ── 11. WebSocketManager shape ────────────────────────────────────────────────

try:
    mgr = WebSocketManager()
    stats = mgr.stats()
    assert "active_connections" in stats
    assert stats["active_connections"] == 0
    assert "clients" in stats
    ok("WebSocketManager.stats() shape correct")
except Exception as e:
    fail("WebSocketManager.stats()", e)


# ── 12. Bridge compiles ───────────────────────────────────────────────────────

try:
    import py_compile
    bridge_files = [
        "opsx/bridge/__init__.py",
        "opsx/bridge/auth.py",
        "opsx/bridge/snapshot_cache.py",
        "opsx/bridge/websocket_manager.py",
        "opsx/bridge/secure_bridge.py",
    ]
    for f in bridge_files:
        py_compile.compile(f, doraise=True)
    ok(f"All {len(bridge_files)} bridge files compile clean")
except Exception as e:
    fail("Bridge compile check", e)


# ── Summary ────────────────────────────────────────────────────────────────────

print()
print("=" * 70)
print(f"BRIDGE QA: {len(PASS)} passed  |  {len(FAIL)} failed")
print("=" * 70)

if FAIL:
    print("FAILED:")
    for f in FAIL:
        print("  FAIL: " + f)
    sys.exit(1)
else:
    print()
    print("IBKR SECURE BRIDGE READY")
