"""
Pre-Omega Final QA — 9-step brutal validation gate.
Verifies: endpoints registered, dashboard IDs, new modules,
real_trade guard, security guardrails, data paths, compilation.
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = []
FAIL = []

def ok(msg): PASS.append(msg); print("  PASS  " + msg)
def fail(msg, exc=None): FAIL.append(msg); print("  FAIL  " + msg + (f"  ({exc})" if exc else ""))

# ── Step 1: All key modules compile ───────────────────────────────────
import py_compile

modules_to_check = [
    "core/trader_alpha_engine.py",
    "core/trader_learning_engine.py",
    "core/portfolio_engine.py",
    "core/portfolio_intelligence_engine.py",
    "core/unified_portfolio_engine.py",
    "core/paper_trading_engine.py",
    "core/proactive_intelligence_engine.py",
    "opsx/connectors/ibkr_connector.py",
    "opsx/connectors/ibkr_readonly.py",
    "opsx/connectors/hapi_readonly.py",
    "main.py",
]

for mod in modules_to_check:
    try:
        py_compile.compile(mod, doraise=True)
        ok(f"Compiles: {mod}")
    except Exception as e:
        fail(f"Compiles: {mod}", e)

# ── Step 2: New module imports ─────────────────────────────────────────
try:
    from core.proactive_intelligence_engine import ProactiveIntelligenceEngine, proactive_intelligence
    ok("core.proactive_intelligence_engine imports")
except Exception as e:
    fail("core.proactive_intelligence_engine imports", e)

try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()
    ok("TraderAlphaEngine instantiates")
except Exception as e:
    fail("TraderAlphaEngine instantiates", e)

# ── Step 3: TraderAlphaEngine new capabilities ─────────────────────────
try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()

    # _detect_market_regime
    import pandas as pd, numpy as np
    close = pd.Series([100 + i*0.5 for i in range(25)])
    regime = engine._detect_market_regime(2.0, close)
    assert "label" in regime
    assert "score_delta" in regime
    assert regime["label"] in ("bull","bear","sideways","panic","high_vol","low_liquidity","unknown")
    ok("TraderAlphaEngine._detect_market_regime() shape")
except Exception as e:
    fail("TraderAlphaEngine._detect_market_regime()", e)

try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()
    pf = engine._portfolio_context_filter("AAPL", 75, None)
    assert pf["adjusted_score"] == 75
    assert pf["delta"] == 0
    ok("TraderAlphaEngine._portfolio_context_filter() no context")
except Exception as e:
    fail("TraderAlphaEngine._portfolio_context_filter()", e)

try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()
    fake_portfolio = {
        "status": "ok",
        "all_positions": [
            {"symbol": "AAPL", "market_value": 25000, "sector": "Technology"},
        ],
        "total_market_value": 50000,
        "total_cash": 10000,
        "concentration_warnings": [],
    }
    pf = engine._portfolio_context_filter("AAPL", 75, fake_portfolio)
    assert pf["already_held"] is True
    assert pf["delta"] < 0  # should penalize — 50% weight
    ok("TraderAlphaEngine._portfolio_context_filter() with holdings")
except Exception as e:
    fail("TraderAlphaEngine._portfolio_context_filter() with holdings", e)

try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()
    import pandas as pd
    close = pd.Series([100.0]*25)
    rsi = engine._rsi(close)
    assert 0 <= rsi <= 100
    ok("TraderAlphaEngine._rsi() valid range")
except Exception as e:
    fail("TraderAlphaEngine._rsi()", e)

# ── Step 4: ProactiveIntelligenceEngine scan ───────────────────────────
try:
    from core.proactive_intelligence_engine import ProactiveIntelligenceEngine
    pie = ProactiveIntelligenceEngine()
    result = pie.scan({})
    assert "alerts" in result
    assert isinstance(result["alerts"], list)
    assert result["real_trade"] is False
    assert "generated_at" in result
    ok("ProactiveIntelligenceEngine.scan() empty context")
except Exception as e:
    fail("ProactiveIntelligenceEngine.scan()", e)

try:
    from core.proactive_intelligence_engine import ProactiveIntelligenceEngine
    pie = ProactiveIntelligenceEngine()
    ctx = {
        "portfolio_snapshot": {
            "status": "ok",
            "total_market_value": 100000,
            "total_daily_pnl": -4500,
            "total_unrealized_pnl": -8000,
            "all_positions": [],
            "concentration_warnings": [
                {"type": "single_name_concentration", "symbol": "NVDA", "weight_pct": 32}
            ],
        },
        "tasks": [
            {"title": "Close Q1 report", "priority": "urgent", "status": "open",
             "updated_at": "2025-01-01T00:00:00"},
        ],
    }
    result = pie.scan(ctx)
    assert result["alert_count"] >= 2, f"Expected >=2 alerts, got {result['alert_count']}"
    assert result["real_trade"] is False
    # Verify portfolio risk alert present
    types = [a["type"] for a in result["alerts"]]
    assert "portfolio_risk" in types
    assert "stale_task" in types
    ok(f"ProactiveIntelligenceEngine.scan() with context ({result['alert_count']} alerts)")
except Exception as e:
    fail("ProactiveIntelligenceEngine.scan() with context", e)

# ── Step 5: main.py new endpoints registered ──────────────────────────
try:
    main_txt = Path("main.py").read_text(encoding="utf-8", errors="replace")
    new_endpoints = [
        "/api/trader/analyze",
        "/api/proactive/alerts",
    ]
    missing = [ep for ep in new_endpoints if ep not in main_txt]
    if missing:
        fail(f"main.py missing endpoints: {missing}")
    else:
        ok(f"main.py has all {len(new_endpoints)} new endpoints")
except Exception as e:
    fail("main.py endpoint check", e)

# ── Step 6: real_trade: False in new engine outputs ────────────────────
try:
    from core.proactive_intelligence_engine import ProactiveIntelligenceEngine
    pie = ProactiveIntelligenceEngine()
    result = pie.scan({})
    assert result.get("real_trade") is False
    ok("ProactiveIntelligenceEngine real_trade: False")
except Exception as e:
    fail("ProactiveIntelligenceEngine real_trade: False", e)

try:
    from core.trader_alpha_engine import TraderAlphaEngine
    engine = TraderAlphaEngine()
    # Test the error path returns real_trade: False
    result = engine._analyze_impl("INVALID_SYM_9999_QA_TEST_XYZ")
    assert result.get("real_trade") is False
    ok("TraderAlphaEngine real_trade: False on error path")
except Exception as e:
    fail("TraderAlphaEngine real_trade: False on error path", e)

# ── Step 7: Security guardrails still intact ──────────────────────────
try:
    from opsx.connectors.ibkr_connector import IBKRConnector, SecurityViolationError
    conn = IBKRConnector()
    blocked = 0
    for method in ["placeOrder", "cancelOrder", "modifyOrder", "place_order",
                   "cancel_order", "modify_order", "transmit_order", "execute_trade", "reqGlobalCancel"]:
        try:
            getattr(conn, method)()
        except SecurityViolationError:
            blocked += 1
    assert blocked == 9
    ok(f"Security guardrails: 9/9 trade methods still blocked")
except Exception as e:
    fail("Security guardrails", e)

# ── Step 8: Dashboard new elements ─────────────────────────────────────
try:
    html = Path("dashboard/jarvis_futuristic.html").read_text(encoding="utf-8")
    required_new = [
        "unified-priority-center",
        "upc-grid",
        "upc-loading",
        "exec-mode-btn",
    ]
    missing = [id_ for id_ in required_new if f'id="{id_}"' not in html]
    if missing:
        fail(f"Dashboard missing new IDs: {missing}")
    else:
        ok(f"Dashboard: all {len(required_new)} new Phase 3 IDs present")
except Exception as e:
    fail("Dashboard new IDs check", e)

try:
    html = Path("dashboard/jarvis_futuristic.html").read_text(encoding="utf-8")
    new_js = [
        "toggleExecutiveMode",
        "loadUnifiedPriorities",
        "applyExecutiveMode",
        "/api/trader/analyze",
        "/api/proactive/alerts",
    ]
    missing_js = [fn for fn in new_js if fn not in html]
    if missing_js:
        fail(f"Dashboard missing new JS: {missing_js}")
    else:
        ok(f"Dashboard: all {len(new_js)} new JS functions/calls present")
except Exception as e:
    fail("Dashboard JS check", e)

# ── Step 9: Data directories writable ─────────────────────────────────
try:
    dirs = [
        Path("data/learning"),
        Path("data/portfolio"),
        Path("reports"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    # reports audit file exists
    assert Path("reports/pre_omega_system_audit.md").exists(), "Audit report missing"
    ok("Data dirs writable + audit report present")
except Exception as e:
    fail("Data dirs + audit report", e)

# ── Summary ────────────────────────────────────────────────────────────
print()
print("=" * 70)
print(f"PRE-OMEGA FINAL QA: {len(PASS)} passed  |  {len(FAIL)} failed")
print("=" * 70)

if FAIL:
    print("FAILED ITEMS:")
    for f in FAIL:
        print("  FAIL: " + f)
    sys.exit(1)
else:
    print()
    print("PRE-OMEGA MATURITY PHASE COMPLETE — READY FOR OMEGA EVOLUTION")
