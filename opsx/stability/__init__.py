"""
JARVIS Production Stability Layer.

Modules:
  production_rules   — runtime safety invariants (real_trade, execution_blocked, etc.)
  api_contract_lock  — API response schema validation and contract hashing
  frontend_qa        — dashboard HTML regression analysis
  startup_validator  — startup-time environment and system validation
  patch_engine       — pre-patch impact analysis and protected feature gating
"""
from opsx.stability.production_rules  import ProductionRules, RuleViolation
from opsx.stability.api_contract_lock import APIContractLock
from opsx.stability.startup_validator import StartupValidator

__all__ = [
    "ProductionRules", "RuleViolation",
    "APIContractLock",
    "StartupValidator",
]
