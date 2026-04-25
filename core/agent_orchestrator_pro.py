from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Pipeline stage definitions — maps each JARVIS stage to the agents whose
# activity signals that stage is in progress.  Ordered: first match wins.
# ---------------------------------------------------------------------------
_STAGE_AGENTS: List[Dict[str, Any]] = [
    {
        "stage":    "SCAN",
        "agents":   {"market_intelligence", "opportunity_radar"},
        "progress": 0.15,
        "label":    "Scanning market data",
    },
    {
        "stage":    "RESEARCH",
        "agents":   {"knowledge_engine", "executive_council"},
        "progress": 0.35,
        "label":    "Researching context and narratives",
    },
    {
        "stage":    "ANALYZE",
        "agents":   {"trader_alpha", "risk_analyst", "wealth_optimizer"},
        "progress": 0.60,
        "label":    "Analyzing signals and scoring setup",
    },
    {
        "stage":    "DECIDE",
        "agents":   {"executive_council", "daily_ops"},
        "progress": 0.82,
        "label":    "Evaluating decision and confidence",
    },
    {
        "stage":    "EXECUTE",
        "agents":   {"trader_alpha"},          # trader_alpha after DECIDE = execution
        "progress": 0.97,
        "label":    "Executing trade plan",
    },
]

# How long (seconds) an activity record keeps a stage "active" before decaying to idle
_ACTIVITY_TTL_S: float = 120.0


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

        # pipeline tracker: last stage written by execute() / execute_trader()
        # { stage, active_agent, message, ts, progress }
        self._pipeline: Dict[str, Any] = {}

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

    # ------------------------------------------------------------------ #
    # Pipeline state                                                       #
    # ------------------------------------------------------------------ #
    def _record_pipeline_stage(self, agent_name: str, message: str) -> None:
        """Write a pipeline state record based on the agent that just activated."""
        now_ts = time.monotonic()
        for stage_def in _STAGE_AGENTS:
            if agent_name in stage_def["agents"]:
                self._pipeline = {
                    "stage":        stage_def["stage"],
                    "progress":     stage_def["progress"],
                    "active_agent": agent_name,
                    "message":      message or stage_def["label"],
                    "ts":           now_ts,
                }
                return
        # Agent not in any stage mapping — record generically under ANALYZE
        self._pipeline = {
            "stage":        "ANALYZE",
            "progress":     0.55,
            "active_agent": agent_name,
            "message":      message or "Processing request",
            "ts":           now_ts,
        }

    def pipeline_state(self) -> Dict[str, Any]:
        """
        Returns the current pipeline stage, derived from real agent activity.

        Three signal sources, in priority order:

        1. A currently-running agent (_last_activity status == "running")
           → immediate, real-time stage
        2. The most recent _pipeline record if within TTL
           → recent activity still relevant
        3. System readiness heuristic from _engine_cache
           → no recent activity; infer from what's loaded
        """
        now_ts = time.monotonic()

        # --- Source 1: actively running agent ---
        for name, act in self._last_activity.items():
            if act.get("status") == "running":
                for stage_def in _STAGE_AGENTS:
                    if name in stage_def["agents"]:
                        return {
                            "stage":        stage_def["stage"],
                            "progress":     stage_def["progress"],
                            "active_agent": name,
                            "message":      act.get("last_action", stage_def["label"]),
                        }
                # running but not in stage map
                return {
                    "stage":        "ANALYZE",
                    "progress":     0.55,
                    "active_agent": name,
                    "message":      act.get("last_action", "Processing"),
                }

        # --- Source 2: recent pipeline record within TTL ---
        if self._pipeline and (now_ts - self._pipeline.get("ts", 0)) < _ACTIVITY_TTL_S:
            p = self._pipeline
            # Decay progress slightly to show the stage completed and is cooling down
            elapsed   = now_ts - p["ts"]
            decay     = min(elapsed / _ACTIVITY_TTL_S, 1.0)
            progress  = round(p["progress"] + (1.0 - p["progress"]) * decay * 0.25, 3)
            return {
                "stage":        p["stage"],
                "progress":     progress,
                "active_agent": p["active_agent"],
                "message":      p["message"],
            }

        # --- Source 3: infer from loaded engines ---
        loaded = set(self._engine_cache.keys())
        if not loaded:
            return {
                "stage":        "SCAN",
                "progress":     0.05,
                "active_agent": "market_intelligence",
                "message":      "System initialising — waiting for first request",
            }

        # Walk stages in reverse to find the deepest stage whose agents are loaded
        for stage_def in reversed(_STAGE_AGENTS):
            if stage_def["agents"] & loaded:
                return {
                    "stage":        stage_def["stage"],
                    "progress":     round(stage_def["progress"] * 0.9, 3),
                    "active_agent": next(iter(stage_def["agents"] & loaded)),
                    "message":      f"{stage_def['label']} — ready, awaiting next request",
                }

        return {
            "stage":        "SCAN",
            "progress":     0.05,
            "active_agent": "market_intelligence",
            "message":      "System ready — no recent activity",
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
        # Record pipeline stage based on which agent is running
        self._record_pipeline_stage(primary, query_snippet)

        result = self._try_methods(engine, query, domain)

        self._last_activity[primary] = {
            "last_action": f"Completed: {query_snippet}" if query_snippet else "Completed request",
            "last_seen": datetime.utcnow().isoformat(),
            "status": "idle",
        }
        # Advance to DECIDE after primary agent completes
        self._record_pipeline_stage("executive_council", f"Evaluating: {query_snippet}")

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

            sym_label = str(symbol_or_prompt).upper()[:12]
            self._last_activity[agent_name] = {
                "last_action": f"Analyzing {sym_label}",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "running",
            }
            self._record_pipeline_stage(agent_name, f"Analyzing {sym_label} momentum")

            result = self._try_methods(engine, symbol_or_prompt, "finance")

            self._last_activity[agent_name] = {
                "last_action": f"Analyzed {sym_label}",
                "last_seen": datetime.utcnow().isoformat(),
                "status": "idle",
            }
            self._record_pipeline_stage("executive_council", f"Deciding on {sym_label}")

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

