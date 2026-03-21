from __future__ import annotations

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
            return instance
        except Exception as e:
            self.boot_events.append(f"failed loading {agent_name}: {e}")
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

        result = self._try_methods(engine, query, domain)

        return {
            "query": query,
            "domain": domain,
            "primary_agent": primary,
            "selected_agents": routed["selected_agents"],
            "summary": f"Executed with primary agent {primary}.",
            "result": result,
        }

    def execute_trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        preferred_agents = ["trader_alpha", "market_intelligence"]

        for agent_name in preferred_agents:
            engine = self._load_engine(agent_name)
            if engine is None:
                continue

            result = self._try_methods(engine, symbol_or_prompt, "finance")

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
