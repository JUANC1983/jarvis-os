"""
Phase 1 Test Suite — IBKR TWS Connector.

Tests cover:
  - SecurityViolationError is raised for ALL blocked methods
  - Guardrail log is written on violation
  - Disconnected responses return correct shape
  - Health check works offline
  - real_trade: False is present in all responses
  - connect() returns structured response even when TWS is offline
  - Snapshot fallback works when disconnected

These tests do NOT require IB Gateway or TWS to be running.
Live-connection tests are skipped unless IBKR_LIVE_TEST=1 env var is set.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from opsx.connectors.ibkr_connector import (
    IBKRConnector,
    SecurityViolationError,
    _classify_asset,
)

LIVE_TEST = os.getenv("IBKR_LIVE_TEST", "0") == "1"
_GUARDRAIL_LOG = Path("data/portfolio/trading_guardrail_log.json")


class TestSecurityViolations(unittest.TestCase):
    """Ensure ALL trade-execution methods are unconditionally blocked."""

    def setUp(self):
        self.connector = IBKRConnector()

    def test_placeOrder_blocked(self):
        with self.assertRaises(SecurityViolationError) as ctx:
            self.connector.placeOrder("dummy_contract", "dummy_order")
        self.assertIn("placeOrder", str(ctx.exception))

    def test_cancelOrder_blocked(self):
        with self.assertRaises(SecurityViolationError) as ctx:
            self.connector.cancelOrder(999)
        self.assertIn("cancelOrder", str(ctx.exception))

    def test_modifyOrder_blocked(self):
        with self.assertRaises(SecurityViolationError) as ctx:
            self.connector.modifyOrder(999, "dummy_contract", "dummy_order")
        self.assertIn("modifyOrder", str(ctx.exception))

    def test_place_order_snake_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.place_order(symbol="AAPL", qty=10, action="BUY")

    def test_cancel_order_snake_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.cancel_order(order_id=42)

    def test_modify_order_snake_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.modify_order(order_id=42, price=150.0)

    def test_transmit_order_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.transmit_order()

    def test_execute_trade_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.execute_trade(symbol="NVDA", qty=5)

    def test_reqGlobalCancel_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.reqGlobalCancel()

    def test_security_violation_message_format(self):
        try:
            self.connector.placeOrder()
        except SecurityViolationError as e:
            self.assertIn("SECURITY VIOLATION", str(e))
            self.assertIn("READ-ONLY", str(e))
            self.assertEqual(e.method, "placeOrder")


class TestGuardrailLogging(unittest.TestCase):
    """SecurityViolationError must write to the guardrail log."""

    def setUp(self):
        self.connector = IBKRConnector()

    def test_guardrail_log_written_on_violation(self):
        try:
            self.connector.placeOrder("test")
        except SecurityViolationError:
            pass

        self.assertTrue(
            _GUARDRAIL_LOG.exists(),
            "Guardrail log file must exist after violation",
        )
        entries = json.loads(_GUARDRAIL_LOG.read_text(encoding="utf-8"))
        self.assertTrue(len(entries) > 0)
        last = entries[-1]
        self.assertEqual(last["method"], "placeOrder")
        self.assertTrue(last["blocked"])
        self.assertIn("timestamp", last)

    def test_guardrail_log_records_multiple_violations(self):
        initial_count = 0
        if _GUARDRAIL_LOG.exists():
            initial_count = len(json.loads(_GUARDRAIL_LOG.read_text(encoding="utf-8")))

        for method_call in [
            lambda: self.connector.placeOrder(),
            lambda: self.connector.cancelOrder(),
            lambda: self.connector.modifyOrder(),
        ]:
            try:
                method_call()
            except SecurityViolationError:
                pass

        entries = json.loads(_GUARDRAIL_LOG.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(entries), initial_count + 3)


class TestDisconnectedState(unittest.TestCase):
    """All read methods must return safe disconnected responses when offline."""

    def setUp(self):
        self.connector = IBKRConnector()
        self.connector._connected = False
        self.connector._ib = None

    def _assert_safe_response(self, result: dict, method: str):
        self.assertIn("status", result, f"{method}: missing 'status'")
        self.assertFalse(
            result.get("real_trade", True),
            f"{method}: real_trade must be False",
        )

    def test_health_check_offline(self):
        result = self.connector.health_check()
        self._assert_safe_response(result, "health_check")
        self.assertFalse(result.get("connected", True))

    def test_get_account_summary_offline(self):
        result = self.connector.get_account_summary()
        self._assert_safe_response(result, "get_account_summary")
        self.assertEqual(result["status"], "disconnected")

    def test_get_positions_offline(self):
        result = self.connector.get_positions()
        self._assert_safe_response(result, "get_positions")
        self.assertEqual(result["status"], "disconnected")

    def test_get_pnl_offline(self):
        result = self.connector.get_pnl()
        self._assert_safe_response(result, "get_pnl")
        self.assertEqual(result["status"], "disconnected")

    def test_get_cash_balance_offline(self):
        result = self.connector.get_cash_balance()
        self._assert_safe_response(result, "get_cash_balance")
        self.assertEqual(result["status"], "disconnected")

    def test_get_full_portfolio_offline_no_cache(self):
        with patch.object(self.connector, "_load_cached_snapshot", return_value=None):
            result = self.connector.get_full_portfolio()
        self._assert_safe_response(result, "get_full_portfolio")
        self.assertEqual(result["status"], "not_connected")
        self.assertEqual(result["positions"], [])

    def test_get_full_portfolio_offline_with_cache(self):
        fake_cache = {
            "status": "ok",
            "positions": [{"symbol": "AAPL", "quantity": 10}],
            "real_trade": False,
        }
        with patch.object(self.connector, "_load_cached_snapshot", return_value=fake_cache):
            result = self.connector.get_full_portfolio()
        self.assertTrue(result.get("_stale"))
        self.assertEqual(result["positions"][0]["symbol"], "AAPL")


class TestConnectOffline(unittest.TestCase):
    """connect() must return structured response even when TWS is not running."""

    def test_connect_returns_structured_error_when_offline(self):
        connector = IBKRConnector(host="127.0.0.1", port=9999, timeout=2.0)
        result = connector.connect()
        self.assertIn("status", result)
        self.assertFalse(result.get("real_trade", True))
        # Should be 'error' since nothing listens on port 9999
        self.assertIn(result["status"], ("error", "disconnected"))

    def test_disconnect_safe_when_not_connected(self):
        connector = IBKRConnector()
        result = connector.disconnect()
        self.assertEqual(result["status"], "disconnected")
        self.assertFalse(result["real_trade"])


class TestRealTradeFlagAlwaysFalse(unittest.TestCase):
    """Every response dict must carry real_trade: False."""

    def setUp(self):
        self.connector = IBKRConnector()

    def test_disconnect_has_real_trade_false(self):
        result = self.connector.disconnect()
        self.assertIs(result["real_trade"], False)

    def test_health_check_has_real_trade_false(self):
        result = self.connector.health_check()
        self.assertIs(result["real_trade"], False)

    def test_connect_error_has_real_trade_false(self):
        connector = IBKRConnector(port=9998, timeout=1.0)
        result = connector.connect()
        self.assertIs(result.get("real_trade"), False)


class TestAssetClassification(unittest.TestCase):
    """_classify_asset must map sec_type strings correctly."""

    def test_stock(self):
        self.assertEqual(_classify_asset("STK"), "equity")

    def test_options(self):
        self.assertEqual(_classify_asset("OPT"), "options")

    def test_futures(self):
        self.assertEqual(_classify_asset("FUT"), "futures")

    def test_forex(self):
        self.assertEqual(_classify_asset("CASH"), "forex")

    def test_fixed_income(self):
        self.assertEqual(_classify_asset("BOND"), "fixed_income")

    def test_crypto(self):
        self.assertEqual(_classify_asset("CRYPTO"), "crypto")

    def test_unknown(self):
        self.assertEqual(_classify_asset("XYZ"), "other")

    def test_case_insensitive(self):
        self.assertEqual(_classify_asset("stk"), "equity")
        self.assertEqual(_classify_asset("Opt"), "options")


@unittest.skipUnless(LIVE_TEST, "Set IBKR_LIVE_TEST=1 to run live tests")
class TestLiveConnection(unittest.TestCase):
    """Live tests — require IB Gateway running on localhost:4002."""

    @classmethod
    def setUpClass(cls):
        cls.connector = IBKRConnector(port=4002, timeout=15.0)
        cls.connect_result = cls.connector.connect()

    @classmethod
    def tearDownClass(cls):
        cls.connector.disconnect()

    def test_live_connect_ok(self):
        self.assertEqual(self.connect_result["status"], "connected")
        self.assertFalse(self.connect_result["real_trade"])

    def test_live_health_check(self):
        result = self.connector.health_check()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["connected"])

    def test_live_account_summary(self):
        result = self.connector.get_account_summary()
        self.assertEqual(result["status"], "ok")
        self.assertIn("net_liquidation", result)
        self.assertFalse(result["real_trade"])

    def test_live_positions(self):
        result = self.connector.get_positions()
        self.assertEqual(result["status"], "ok")
        self.assertIsInstance(result["positions"], list)
        self.assertFalse(result["real_trade"])

    def test_live_pnl(self):
        result = self.connector.get_pnl()
        self.assertEqual(result["status"], "ok")
        self.assertIn("daily_pnl", result)

    def test_live_cash_balance(self):
        result = self.connector.get_cash_balance()
        self.assertEqual(result["status"], "ok")
        self.assertIn("total_cash", result)

    def test_live_placeOrder_still_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.placeOrder()

    def test_live_cancelOrder_still_blocked(self):
        with self.assertRaises(SecurityViolationError):
            self.connector.cancelOrder()


if __name__ == "__main__":
    print("=" * 60)
    print("IBKR TWS Connector — Phase 1 Test Suite")
    print("=" * 60)
    print(f"Live tests: {'ENABLED' if LIVE_TEST else 'SKIPPED (set IBKR_LIVE_TEST=1)'}")
    print()
    unittest.main(verbosity=2)
