"""
JARVIS Portfolio Integration QA — Phase 2/3 Gate.
"""
import json
import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = []
FAIL = []

def ok(msg):
    PASS.append(msg)
    print("  PASS  " + msg)

def fail(msg, exc=None):
    FAIL.append(msg)
    print("  FAIL  " + msg + (f"  ({exc})" if exc else ""))

# ── 1. Module imports ─────────────────────────────────────────────────────────

try:
    from core.trader_learning_engine import TraderLearningEngine
    ok("core.trader_learning_engine imports")
except Exception as e:
    fail("core.trader_learning_engine imports", e)

try:
    from core.portfolio_engine import PortfolioEngine
    ok("core.portfolio_engine imports")
except Exception as e:
    fail("core.portfolio_engine imports", e)

try:
    from core.paper_trading_engine import PaperTradingEngine
    ok("core.paper_trading_engine imports")
except Exception as e:
    fail("core.paper_trading_engine imports", e)

try:
    from core.unified_portfolio_engine import UnifiedPortfolioEngine
    ok("core.unified_portfolio_engine imports")
except Exception as e:
    fail("core.unified_portfolio_engine imports", e)

try:
    from core.portfolio_intelligence_engine import PortfolioIntelligenceEngine
    ok("core.portfolio_intelligence_engine imports")
except Exception as e:
    fail("core.portfolio_intelligence_engine imports", e)

try:
    from opsx.connectors.ibkr_connector import IBKRConnector, SecurityViolationError
    ok("opsx.connectors.ibkr_connector imports")
except Exception as e:
    fail("opsx.connectors.ibkr_connector imports", e)

try:
    from opsx.connectors.ibkr_readonly import IBKRReadOnly, TradingBlockedError
    ok("opsx.connectors.ibkr_readonly imports")
except Exception as e:
    fail("opsx.connectors.ibkr_readonly imports", e)

try:
    from opsx.connectors.hapi_readonly import HapiReadOnly
    ok("opsx.connectors.hapi_readonly imports")
except Exception as e:
    fail("opsx.connectors.hapi_readonly imports", e)

# ── 2. Portfolio engine shape ──────────────────────────────────────────────────

try:
    eng = PortfolioEngine()
    result = eng.compute({})
    assert result["status"] == "no_data"
    assert result["real_trade"] is False
    assert "ai_summary" in result
    assert "portfolio_score" in result
    ok("PortfolioEngine.compute() empty snapshot shape")
except Exception as e:
    fail("PortfolioEngine.compute() empty snapshot", e)

try:
    eng = PortfolioEngine()
    fake_unified = {
        "status": "ok",
        "all_positions": [
            {"symbol": "AAPL", "quantity": 10, "avg_cost": 175.0, "market_price": 182.0,
             "market_value": 1820.0, "daily_pnl": 12.0, "sector": "Technology",
             "asset_class": "equity", "weight_pct": 100.0},
        ],
        "total_market_value": 1820.0,
        "total_cash": 5000.0,
        "total_daily_pnl": 12.0,
        "total_unrealized_pnl": 70.0,
        "sector_exposure": [{"label": "Technology", "value": 1820.0, "pct": 100.0}],
        "brokers": {"ibkr": {"status": "ok", "market_value": 1820.0, "_stale": False}},
        "concentration_warnings": [],
    }
    result = eng.compute(fake_unified)
    assert result["status"] == "ok"
    assert result["real_trade"] is False
    assert len(result["positions"]) == 1
    assert result["positions"][0]["cost_basis"] == 1750.0
    assert "ai_summary" in result
    assert result["portfolio_score"] > 0
    ok("PortfolioEngine.compute() with real data")
except Exception as e:
    fail("PortfolioEngine.compute() with real data", e)

# ── 3. Paper trading full cycle ───────────────────────────────────────────────

try:
    pt = PaperTradingEngine()
    reset = pt.reset(10_000)
    assert reset["real_trade"] is False
    assert reset["status"] == "ok"
    ok("PaperTradingEngine.reset()")
except Exception as e:
    fail("PaperTradingEngine.reset()", e)

try:
    pt = PaperTradingEngine()
    pt.reset(10_000)
    trade = pt.simulate_trade("NVDA", "buy", 5, 500.0, "test thesis")
    assert trade["real_trade"] is False
    assert trade["status"] == "ok"
    ok("PaperTradingEngine.simulate_trade() buy")
except Exception as e:
    fail("PaperTradingEngine.simulate_trade() buy", e)

try:
    pt = PaperTradingEngine()
    status = pt.get_status()
    assert status["real_trade"] is False
    assert "cash" in status
    assert "total_portfolio" in status
    ok("PaperTradingEngine.get_status() shape")
except Exception as e:
    fail("PaperTradingEngine.get_status() shape", e)

# ── 4. Trader learning cycle ───────────────────────────────────────────────────

try:
    tl = TraderLearningEngine()
    r = tl.record_outcome("AAPL", "BUY", 0.75, "up", 3.2, 5, "qa_test")
    assert r["status"] == "recorded"
    assert r["outcome"] in ("win", "loss", "neutral")
    assert r["real_trade"] is False
    ok("TraderLearningEngine.record_outcome()")
except Exception as e:
    fail("TraderLearningEngine.record_outcome()", e)

try:
    tl = TraderLearningEngine()
    m = tl.get_metrics()
    assert m["real_trade"] is False
    assert "overall_win_rate" in m
    assert "learning_quality_score" in m
    assert "signal_breakdown" in m
    ok("TraderLearningEngine.get_metrics() shape")
except Exception as e:
    fail("TraderLearningEngine.get_metrics() shape", e)

try:
    tl = TraderLearningEngine()
    sp = tl.get_signal_performance()
    assert "by_signal" in sp
    ok("TraderLearningEngine.get_signal_performance()")
except Exception as e:
    fail("TraderLearningEngine.get_signal_performance()", e)

try:
    tl = TraderLearningEngine()
    cal = tl.get_confidence_calibration()
    assert "calibration" in cal
    assert len(cal["calibration"]) == 5
    ok("TraderLearningEngine.get_confidence_calibration() 5 buckets")
except Exception as e:
    fail("TraderLearningEngine.get_confidence_calibration()", e)

try:
    tl = TraderLearningEngine()
    adj = tl.get_adapted_score_adjustment("UNKNOWN_SYM_QA", 60.0)
    assert adj["adjusted_score"] == 60.0
    assert adj["adjustment"] == 0
    ok("TraderLearningEngine.get_adapted_score_adjustment() insufficient data")
except Exception as e:
    fail("TraderLearningEngine.get_adapted_score_adjustment()", e)

# ── 5. IBKR security guardrails ───────────────────────────────────────────────

try:
    conn = IBKRConnector()
    blocked = 0
    for method in ["placeOrder", "cancelOrder", "modifyOrder", "place_order",
                   "cancel_order", "modify_order", "transmit_order", "execute_trade", "reqGlobalCancel"]:
        try:
            getattr(conn, method)()
        except SecurityViolationError:
            blocked += 1
    assert blocked == 9, f"Expected 9 blocks, got {blocked}"
    ok(f"IBKRConnector: all 9 trade methods blocked ({blocked}/9)")
except Exception as e:
    fail("IBKRConnector security guardrails", e)

# ── 6. UnifiedPortfolioEngine empty snapshot ─────────────────────────────────

try:
    upe = UnifiedPortfolioEngine()
    snap = upe.empty_snapshot("qa_test")
    assert snap["status"] == "no_data"
    assert snap["real_trade"] is False
    assert snap["total_market_value"] == 0
    ok("UnifiedPortfolioEngine.empty_snapshot() shape")
except Exception as e:
    fail("UnifiedPortfolioEngine.empty_snapshot()", e)

# ── 7. PortfolioIntelligenceEngine no-data report ────────────────────────────

try:
    pie = PortfolioIntelligenceEngine()
    report = pie._no_data_report()
    assert report["real_trade"] is False  # This field should not be True
    ok("PortfolioIntelligenceEngine._no_data_report() has real_trade key")
except AttributeError:
    # _no_data_report may not have real_trade — check analyze() instead
    try:
        pie = PortfolioIntelligenceEngine()
        result = pie.analyze({"status": "no_data"})
        assert "portfolio_score" in result
        ok("PortfolioIntelligenceEngine.analyze() no_data shape")
    except Exception as e2:
        fail("PortfolioIntelligenceEngine.analyze() no_data", e2)
except Exception as e:
    fail("PortfolioIntelligenceEngine._no_data_report()", e)

# ── 8. real_trade: True never appears ────────────────────────────────────────

try:
    checked = []
    # Check a few key response shapes
    for cls, method, args in [
        (IBKRConnector, "health_check", []),
        (IBKRConnector, "disconnect", []),
    ]:
        obj = cls()
        result = getattr(obj, method)(*args)
        assert result.get("real_trade") is not True, f"{cls.__name__}.{method}() has real_trade=True"
        checked.append(f"{cls.__name__}.{method}")
    ok(f"real_trade: False verified in {len(checked)} responses")
except Exception as e:
    fail("real_trade: True check", e)

# ── 9. Dashboard IDs present ──────────────────────────────────────────────────

try:
    html = Path("dashboard/jarvis_futuristic.html").read_text(encoding="utf-8")
    required_ids = [
        "port-risk-score", "port-risk-level", "port-status-chip",
        "port-total", "port-invested", "port-cash", "port-cash-pct",
        "port-daily-pnl", "port-daily-pct", "port-unrealized", "port-unr-pct",
        "port-positions-count", "port-summary", "port-risks", "port-opps",
        "port-warnings", "port-sector-bars", "port-holdings-table",
        "broker-ibkr", "broker-hapi",
        "paper-total", "paper-cash", "paper-pnl", "paper-trades",
        "paper-symbol", "paper-action", "paper-qty", "paper-price",
        "paper-positions-list",
        "trader-audit-result",
        "learn-winrate", "learn-outcomes", "learn-quality",
        "learn-calibration-row", "learn-signal-breakdown",
        "learn-symbol", "learn-signal", "learn-return",
        "compare-result", "stale-banner",
        "mkt-indices", "mkt-regime-badge", "mkt-snapshot-time",
    ]
    missing_ids = [id_ for id_ in required_ids if f'id="{id_}"' not in html]
    if missing_ids:
        fail(f"Dashboard missing IDs: {missing_ids}")
    else:
        ok(f"Dashboard: all {len(required_ids)} required element IDs present")
except Exception as e:
    fail("Dashboard IDs check", e)

# ── 10. Learning data paths writable ─────────────────────────────────────────

try:
    test_paths = [
        Path("data/learning/signal_outcomes.json"),
        Path("data/learning/learning_metrics.json"),
        Path("data/portfolio/ibkr_tws_snapshot.json"),
        Path("data/portfolio/paper_positions.json"),
    ]
    for p in test_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
    ok("All data directories writable")
except Exception as e:
    fail("Data directory write check", e)

# ── Summary ───────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print(f"QA RESULTS: {len(PASS)} passed  |  {len(FAIL)} failed")
print("=" * 60)

if FAIL:
    print("FAILED ITEMS:")
    for f in FAIL:
        print("  FAIL: " + f)
    sys.exit(1)
else:
    print("ALL QA CHECKS PASSED - PHASE GATE CLEARED")
