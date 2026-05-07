"""
JARVIS Paper Trading OS — Full QA Suite (Phase 8)
Tests: UX structure, safety guardrails, engine integrity, stress scenarios.
"""
import re, sys, os, time
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


# ── 1. Dashboard HTML structural audit ──────────────────────────────────

html = Path("dashboard/jarvis_futuristic.html").read_text(encoding="utf-8")

# Safety: no real trading endpoints
for blocked in ["placeOrder", "cancelOrder", "modifyOrder", "/api/trade/execute", "/api/broker/order"]:
    if blocked in html:
        fail(f"SECURITY: real trading ref found: {blocked}")
    else:
        ok(f"No real trading ref: {blocked}")

# Sub-navigation panels
for panel in ["cockpit", "lab", "learning", "analysis"]:
    if f"mkt-panel-{panel}" in html and f"mkt-nav-{panel}" in html:
        ok(f"Sub-panel + nav button: {panel}")
    else:
        fail(f"Missing sub-panel or nav: {panel}")

# Required metric IDs
required_ids = [
    "ck-real-total", "ck-paper-total", "ck-daily-pnl", "ck-unrealized",
    "ck-risk-score", "ck-insights-stream", "ck-sector-bars", "ck-broker-chips",
    "lab-win-rate", "lab-avg-gain", "lab-avg-loss", "lab-rr", "lab-drawdown",
    "lab-open-pos", "lab-closed", "lab-ai-conf", "lab-equity-chart",
    "lc-total", "lc-accuracy", "lc-bull-acc", "lc-bear-acc", "lc-calibration",
    "lc-avg-ret", "lc-trend", "lc-calibration-chart", "lc-signal-chart",
    "lc-best-setups", "lc-worst-setups", "lc-narrative",
    "trader-explain-block", "paper-stop", "paper-tp", "paper-strategy",
    "lab-trade-feedback", "lab-strategy-table", "lab-trade-history",
]
for id_ in required_ids:
    cnt = html.count(f'id="{id_}"')
    if cnt == 1:   ok(f"ID exists once: {id_}")
    elif cnt == 0: fail(f"Missing ID: {id_}")
    else:          warn(f"Duplicate ID ({cnt}x): {id_}")

# Critical shared IDs must appear exactly once
critical = [
    "symbolInput", "analyzeBtn", "mkt-indices", "paper-positions-list",
    "traderSymbol", "setupScore", "trafficLightText", "priceNow",
    "recommendations", "mkt-news", "trader-audit-result",
]
for id_ in critical:
    cnt = html.count(f'id="{id_}"')
    if cnt == 1:   ok(f"Critical ID unique: {id_}")
    elif cnt == 0: fail(f"Critical ID missing: {id_}")
    else:          warn(f"Duplicate critical ID ({cnt}x): {id_}")

# Chart.js loaded and used
if "chart.js@4" in html and "new Chart(" in html:
    ok("Chart.js loaded and used")
else:
    fail("Chart.js missing or not used")

# New JS functions
for fn in ["switchMarketPanel", "loadCockpit", "loadPaperAnalytics",
           "loadLearningFull", "_renderExplainBlock", "_renderEquityChart",
           "_initMarketsTab", "_renderCalibrationChart"]:
    if f"function {fn}" in html:
        ok(f"JS function defined: {fn}")
    else:
        fail(f"JS function missing: {fn}")

# CSS components
for cls in ["mkt-subnav", "hero-card", "metric-card", "exec-form",
            "insight-item", "chart-box", "explain-block", "live-dot"]:
    if f".{cls}" in html:
        ok(f"CSS class defined: .{cls}")
    else:
        fail(f"CSS class missing: .{cls}")


# ── 2. Engine safety tests ───────────────────────────────────────────────

try:
    from core.paper_trading_engine import PaperTradingEngine
    engine = PaperTradingEngine()
    s = engine.get_status()
    assert s.get("real_trade") is False
    ok("Paper engine: real_trade: False in status")
except Exception as e:
    fail(f"Paper engine status: {e}")

try:
    r = engine.simulate_trade("AAPL", "buy", -1, 100)
    assert r.get("status") == "error" and r.get("real_trade") is False
    ok("Paper engine: negative qty rejected correctly")
except Exception as e:
    fail(f"Paper engine neg qty: {e}")

try:
    r = engine.simulate_trade("AAPL", "placeOrder", 1, 100)
    assert r.get("status") == "error" and r.get("real_trade") is False
    ok("Paper engine: 'placeOrder' action blocked")
except Exception as e:
    fail(f"Paper engine blocked action: {e}")

try:
    r = engine.simulate_trade("AAPL", "buy", 1, 0)
    assert r.get("status") == "error"
    ok("Paper engine: zero price rejected")
except Exception as e:
    fail(f"Paper engine zero price: {e}")

# All outputs have real_trade: False
try:
    results = [
        engine.get_status().get("real_trade"),
        engine.get_positions().get("real_trade"),
        engine.get_performance().get("real_trade"),
        engine.get_history().get("real_trade"),
        engine.compare_with_real({}).get("real_trade"),
    ]
    assert all(v is False for v in results), f"Not all False: {results}"
    ok("Paper engine: real_trade: False in ALL 5 methods")
except Exception as e:
    fail(f"Paper engine real_trade guarantee: {e}")


# ── 3. Learning engine tests ─────────────────────────────────────────────

try:
    from core.trader_learning_engine import TraderLearningEngine
    le = TraderLearningEngine()
    m = le.get_metrics()
    assert m.get("real_trade") is False
    ok("Learning engine: real_trade: False in metrics")
except Exception as e:
    fail(f"Learning engine metrics: {e}")

try:
    sp = le.get_signal_performance()
    assert sp.get("real_trade") is False
    ok("Learning engine: real_trade: False in signal_performance")
except Exception as e:
    fail(f"Learning engine signal_performance: {e}")

try:
    adj = le.get_adapted_score_adjustment("AAPL_NONEXISTENT_999", 55.0)
    # With no data for this symbol: unchanged score
    assert adj.get("adjusted_score") == 55.0
    assert adj.get("confidence") == "insufficient_data"
    ok("Learning engine: no-data symbol returns unchanged score")
except Exception as e:
    fail(f"Learning engine no-data adj: {e}")

try:
    # 500+ records performance
    outcomes = [
        {"outcome": "win" if i%3 != 0 else "loss", "confidence": 0.65,
         "actual_return_pct": 2.0 if i%3 != 0 else -1.5,
         "signal_type": "BUY", "holding_days": 5}
        for i in range(600)
    ]
    t0 = time.monotonic()
    metrics = le._recompute_metrics(outcomes)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"Too slow: {elapsed:.3f}s"
    assert metrics.get("total_outcomes") == 600
    ok(f"Learning engine: 600 outcomes recomputed in {elapsed*1000:.0f}ms")
except Exception as e:
    fail(f"Learning engine 600 records: {e}")


# ── 4. Portfolio intelligence tests ──────────────────────────────────────

try:
    from core.portfolio_intelligence_engine import PortfolioIntelligenceEngine
    pie = PortfolioIntelligenceEngine()
    r = pie.analyze({"status": "no_data"})
    assert r.get("portfolio_score") == 0
    ok("Portfolio intelligence: no_data handled gracefully")
except Exception as e:
    fail(f"Portfolio intelligence no_data: {e}")

try:
    r = pie.analyze({})
    assert r.get("portfolio_score") == 0
    ok("Portfolio intelligence: empty snapshot handled")
except Exception as e:
    fail(f"Portfolio intelligence empty: {e}")


# ── 5. Bridge security (compile + no execution paths) ────────────────────

try:
    import py_compile
    bridge_files = [
        "opsx/bridge/secure_bridge.py",
        "opsx/bridge/auth.py",
        "opsx/bridge/snapshot_cache.py",
        "opsx/bridge/websocket_manager.py",
    ]
    for f in bridge_files:
        py_compile.compile(f, doraise=True)
    ok(f"All {len(bridge_files)} bridge files compile clean")
except Exception as e:
    fail(f"Bridge compile: {e}")

try:
    from opsx.bridge.secure_bridge import (
        placeOrder, cancelOrder, modifyOrder, SecurityViolationError
    )
    blocked = 0
    for fn in [placeOrder, cancelOrder, modifyOrder]:
        try: fn()
        except SecurityViolationError: blocked += 1
    assert blocked == 3
    ok("Bridge: 3 execution methods blocked with SecurityViolationError")
except Exception as e:
    fail(f"Bridge execution block: {e}")


# ── 6. Main.py compile + endpoint presence ───────────────────────────────

try:
    import py_compile
    py_compile.compile("main.py", doraise=True)
    ok("main.py compiles clean")
except Exception as e:
    fail(f"main.py compile: {e}")

try:
    src = Path("main.py").read_text(encoding="utf-8")
    new_endpoints = [
        "/api/paper/analytics",
        "/api/portfolio/cockpit",
        "_build_ai_insights",
        "_compute_equity_curve",
    ]
    for ep in new_endpoints:
        assert ep in src, f"Missing: {ep}"
    ok(f"main.py: all {len(new_endpoints)} new endpoints/helpers present")
except Exception as e:
    fail(f"main.py new endpoints: {e}")


# ── 7. Stress test: stale / empty / disconnected ─────────────────────────

try:
    # Empty compare_with_real (no real portfolio connected)
    r = engine.compare_with_real({})
    assert r.get("real_trade") is False
    ok("Paper engine: compare_with_real empty snapshot graceful")
except Exception as e:
    fail(f"compare_with_real empty: {e}")

try:
    # Rebalance with zero portfolio
    r = engine.rebalance({"AAPL": 50.0}, {"AAPL": 185.0})
    assert r.get("real_trade") is False
    ok("Paper engine: rebalance graceful with zero portfolio")
except Exception as e:
    fail(f"Paper engine rebalance: {e}")


# ── Summary ───────────────────────────────────────────────────────────────

print()
print("=" * 70)
print(f"JARVIS PAPER OS QA: {len(PASS)} passed | {len(WARN)} warnings | {len(FAIL)} failed")
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
    print("JARVIS PAPER TRADING OS READY")
