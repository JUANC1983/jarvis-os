from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class AgentOrchestratorPro:
    def __init__(self) -> None:
        self.agent_registry = {
            "finance": ["market_intelligence", "opportunity_radar", "wealth_optimizer", "risk_analyst", "trader_alpha"],
            "medical": ["medical_supreme", "fitness_performance"],
            "legal": ["legal_compliance"],
            "general": ["executive_council", "daily_ops", "knowledge_engine"],
            "macro": ["market_intelligence", "risk_analyst", "executive_council", "trader_alpha"],
        }

        self.agent_reputation = {
            "market_intelligence": 0.90,
            "opportunity_radar": 0.88,
            "wealth_optimizer": 0.86,
            "risk_analyst": 0.92,
            "trader_alpha": 0.89,
            "medical_supreme": 0.78,
            "fitness_performance": 0.82,
            "legal_compliance": 0.84,
            "executive_council": 0.91,
            "daily_ops": 0.80,
            "knowledge_engine": 0.79,
        }

        self.engine_map: Dict[str, Tuple[str, str]] = {
            "market_intelligence": ("core.market_intelligence_engine", "MarketIntelligenceEngine"),
            "opportunity_radar": ("core.opportunity_radar_engine", "OpportunityRadarEngine"),
            "wealth_optimizer": ("core.wealth_optimizer", "WealthOptimizer"),
            "risk_analyst": ("core.global_risk_monitor", "GlobalRiskMonitor"),
            "trader_alpha": ("core.trader_alpha_engine", "TraderAlphaEngine"),
            "medical_supreme": ("core.medical_supreme_engine", "MedicalSupremeEngine"),
            "fitness_performance": ("core.fitness_performance_engine", "FitnessPerformanceEngine"),
            "legal_compliance": ("core.legal_compliance_engine", "LegalComplianceEngine"),
            "executive_council": ("core.real_agent_council", "RealAgentCouncil"),
            "daily_ops": ("core.daily_ops_engine", "DailyOpsEngine"),
            "knowledge_engine": ("core.knowledge_engine", "KnowledgeEngine"),
        }

        self._engine_cache: Dict[str, Any] = {}
        self.boot_events: List[str] = []

        # lightweight per-agent activity tracker: name → {last_action, last_seen, status}
        self._last_activity: Dict[str, Dict[str, Any]] = {}

    def route(self, domain: str) -> Dict[str, Any]:
        selected = self.agent_registry.get(domain, self.agent_registry["general"])
        weighted = [
            {"agent": agent, "reputation": self.agent_reputation.get(agent, 0.75)}
            for agent in selected
        ]
        weighted = sorted(weighted, key=lambda x: x["reputation"], reverse=True)

        return {
            "domain": domain,
            "selected_agents": weighted,
            "primary_agent": weighted[0]["agent"] if weighted else "executive_council",
        }

    def deliberate(self, query: str, domain: str = "general") -> Dict[str, Any]:
        routed = self.route(domain)
        return {
            "query": query,
            "domain": domain,
            "primary_agent": routed["primary_agent"],
            "selected_agents": routed["selected_agents"],
            "summary": f"AgentOrchestratorPro routed this request to {len(routed['selected_agents'])} specialized agents.",
        }

    def health(self) -> Dict[str, Any]:
        return {
            "available": True,
            "loaded_engines": list(self._engine_cache.keys()),
            "boot_events": self.boot_events,
        }

    def agent_status_snapshot(self) -> List[Dict[str, Any]]:
        """
        Returns a live status snapshot for every known agent.

        Status derivation (no hardcoding — driven by registry + runtime state):
          - "error"   : engine failed to load (recorded in boot_events)
          - "running" : engine is currently executing (set in execute / execute_trader)
          - "idle"    : engine has been loaded and is ready
          - "standby" : engine not yet instantiated this session
        """
        try:
            from core.premium_agent_registry import PremiumAgentRegistry
            registry_meta = PremiumAgentRegistry().list_agents()
        except Exception:
            registry_meta = {}

        # Role descriptions are the best human-readable "last_action" fallback
        role_descriptions: Dict[str, str] = {
            name: meta.get("role", "Ready") for name, meta in registry_meta.items()
        }

        # Build the set of all known agents from both sources
        all_agents = set(self.agent_reputation.keys()) | set(registry_meta.keys())

        # Derive which agents errored from boot_events
        errored: set = set()
        for event in self.boot_events:
            if event.startswith("failed loading "):
                name = event.split("failed loading ", 1)[1].split(":")[0].strip()
                errored.add(name)

        items: List[Dict[str, Any]] = []

        for name in sorted(all_agents):
            activity = self._last_activity.get(name)

            if activity:
                status = activity["status"]
                last_action = activity["last_action"]
            elif name in errored:
                status = "error"
                last_action = "Failed to load engine"
            elif name in self._engine_cache:
                status = "idle"
                last_action = role_descriptions.get(name, "Ready")
            else:
                status = "standby"
                last_action = role_descriptions.get(name, "Waiting for activation")

            confidence = self.agent_reputation.get(
                name,
                registry_meta.get(name, {}).get("reputation", 0.75)
            )

            items.append({
                "name": name,
                "status": status,
                "last_action": last_action,
                "confidence": round(confidence, 2),
            })

        # Sort: running first, then idle, then standby, then error
        order = {"running": 0, "idle": 1, "standby": 2, "error": 3}
        items.sort(key=lambda x: (order.get(x["status"], 9), x["name"]))

        return items

    def _load_engine(self, agent_name: str) -> Optional[Any]:
        if agent_name in self._engine_cache:
            return self._engine_cache[agent_name]

        engine_info = self.engine_map.get(agent_name)
        if not engine_info:
            self.boot_events.append(f"engine mapping missing: {agent_name}")
            return None

        module_name, class_name = engine_info

        try:
            module = __import__(module_name, fromlist=[class_name])
            klass = getattr(module, class_name)
            instance = klass()
            self._engine_cache[agent_name] = instance
            self.boot_events.append(f"loaded: {agent_name}")
            self._last_activity[agent_name] = {
                "last_action": "Engine loaded",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "idle",
            }
            return instance
        except Exception as e:
            self.boot_events.append(f"failed loading {agent_name}: {e}")
            self._last_activity[agent_name] = {
                "last_action": f"Load error: {type(e).__name__}",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "error",
            }
            return None

    def _try_methods(self, engine: Any, query: str, domain: str) -> Any:
        candidates = [
            ("analyze", [query]),
            ("analyze", [query, domain]),
            ("run", [query]),
            ("run", [query, domain]),
            ("process", [query]),
            ("process", [query, domain]),
            ("optimize", [query]),
            ("summary", []),
            ("deliberate", [query, domain, "Juan Camilo"]),
            ("deliberate", [query, domain]),
            ("get_knowledge", [query]),
        ]

        for method_name, args in candidates:
            method = getattr(engine, method_name, None)
            if callable(method):
                try:
                    return method(*args)
                except TypeError:
                    continue
                except Exception as e:
                    return {"error": str(e), "source": engine.__class__.__name__}

        return {
            "error": f"No compatible method found for {engine.__class__.__name__}",
            "source": engine.__class__.__name__,
        }

    def execute(self, query: str, domain: str = "general") -> Dict[str, Any]:
        routed = self.route(domain)
        primary = routed["primary_agent"]

        engine = self._load_engine(primary)
        if engine is None:
            return {
                "query": query,
                "domain": domain,
                "primary_agent": primary,
                "selected_agents": routed["selected_agents"],
                "summary": f"Primary agent {primary} not available.",
                "result": None,
            }

        query_snippet = (query or "")[:60].strip()
        self._last_activity[primary] = {
            "last_action": f"Processing: {query_snippet}" if query_snippet else "Processing request",
            "last_seen": datetime.utcnow().isoformat(),
            "status": "running",
        }

        result = self._try_methods(engine, query, domain)

        self._last_activity[primary] = {
            "last_action": f"Completed: {query_snippet}" if query_snippet else "Completed request",
            "last_seen": datetime.utcnow().isoformat(),
            "status": "idle",
        }

        return {
            "query": query,
            "domain": domain,
            "primary_agent": primary,
            "selected_agents": routed["selected_agents"],
            "summary": f"Executed with primary agent {primary}.",
            "result": result,
        }

    def execute_trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        preferred_agents = ["premium_trader", "trader_alpha"]

        for agent_name in preferred_agents:
            engine = self._load_engine(agent_name)
            if engine is None:
                continue

            self._last_activity[agent_name] = {
                "last_action": f"Analyzing {str(symbol_or_prompt).upper()[:12]}",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "running",
            }

            result = self._try_methods(engine, symbol_or_prompt, "finance")

            self._last_activity[agent_name] = {
                "last_action": f"Analyzed {str(symbol_or_prompt).upper()[:12]}",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "idle",
            }

            if isinstance(result, dict):
                result.setdefault("symbol", str(symbol_or_prompt).upper())
                result.setdefault("source", agent_name)
                result.setdefault("setup_score", result.get("score"))
                result.setdefault("traffic_light", result.get("traffic_light", "green" if result.get("setup_score") else "orange"))
                result.setdefault("technicals", {"price": result.get("price")})
                result.setdefault(
                    "trade_plan",
                    {
                        "action": result.get("action", "-"),
                        "entry_zone": result.get("entry_zone", []),
                        "stop_loss": result.get("stop_loss", "-"),
                        "target_1": result.get("target_1", "-"),
                        "target_2": result.get("target_2", "-"),
                        "risk_reward_estimate": result.get("risk_reward_estimate", "-"),
                    },
                )
                result.setdefault("narrative", [result.get("summary")] if result.get("summary") else [])
                return result

            if isinstance(result, str):
                return {
                    "symbol": str(symbol_or_prompt).upper(),
                    "setup_score": None,
                    "traffic_light": "orange",
                    "technicals": {"price": None},
                    "trade_plan": {
                        "action": "-",
                        "entry_zone": [],
                        "stop_loss": "-",
                        "target_1": "-",
                        "target_2": "-",
                        "risk_reward_estimate": "-",
                    },
                    "narrative": [result],
                    "summary": result,
                    "source": agent_name,
                }

        return {
            "symbol": str(symbol_or_prompt).upper(),
            "setup_score": None,
            "traffic_light": "red",
            "technicals": {"price": None},
            "trade_plan": {
                "action": "-",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "narrative": ["Trader engines unavailable."],
            "summary": "Trader engines unavailable.",
            "source": "fallback",
        }

