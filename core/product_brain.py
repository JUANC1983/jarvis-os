from __future__ import annotations

from typing import Any, Dict, Optional


class ProductBrain:
    """
    Safe product brain for JARVIS presentation build.

    Goals:
    - Do not break existing agents
    - Reuse current core modules if available
    - Fall back gracefully when a module/method is missing
    - Produce better structured responses for product demo
    """

    def __init__(self) -> None:
        self.boot_events = []

        self.conversation = self._safe_instance("core.conversation_engine", "ConversationEngine")
        self.intent_router = self._safe_instance("core.intent_ai_router", "IntentAIRouter")
        self.agent_orchestrator = self._safe_instance("core.agent_orchestrator_pro", "AgentOrchestratorPro")
        self.trader_alpha = self._safe_instance("core.trader_alpha_engine", "TraderAlphaEngine")
        self.market_intelligence = self._safe_instance("core.market_intelligence_engine", "MarketIntelligenceEngine")
        self.portfolio_brain = self._safe_instance("core.portfolio_brain", "PortfolioBrain")
        self.global_opportunity = self._safe_instance("core.global_opportunity_radar_pro", "GlobalOpportunityRadarPro")
        self.geopolitical = self._safe_instance("core.geopolitical_intelligence_engine", "GeopoliticalIntelligenceEngine")
        self.executive_briefing = self._safe_instance("core.executive_briefing_engine", "ExecutiveBriefingEngine")

    def _safe_instance(self, module_name: str, class_name: str) -> Optional[Any]:
        try:
            module = __import__(module_name, fromlist=[class_name])
            klass = getattr(module, class_name)
            instance = klass()
            self.boot_events.append(f"loaded {module_name}.{class_name}")
            return instance
        except Exception as e:
            self.boot_events.append(f"failed {module_name}.{class_name}: {e}")
            return None

    def _call_first(self, obj: Any, attempts: list[tuple[str, tuple]]) -> Any:
        if obj is None:
            return None

        for method_name, args in attempts:
            method = getattr(obj, method_name, None)
            if callable(method):
                try:
                    return method(*args)
                except TypeError:
                    continue
                except Exception:
                    continue
        return None

    def health(self) -> Dict[str, Any]:
        return {
            "available": True,
            "boot_events": self.boot_events,
            "loaded": {
                "conversation": self.conversation is not None,
                "intent_router": self.intent_router is not None,
                "agent_orchestrator": self.agent_orchestrator is not None,
                "trader_alpha": self.trader_alpha is not None,
                "market_intelligence": self.market_intelligence is not None,
                "portfolio_brain": self.portfolio_brain is not None,
                "global_opportunity": self.global_opportunity is not None,
                "geopolitical": self.geopolitical is not None,
                "executive_briefing": self.executive_briefing is not None,
            },
        }

    def detect_domain(self, message: str) -> str:
        msg = (message or "").lower()

        # Prefer existing intent router if compatible
        routed = self._call_first(
            self.intent_router,
            [
                ("route", (message,)),
                ("detect", (message,)),
                ("classify", (message,)),
                ("analyze", (message,)),
            ],
        )

        if isinstance(routed, dict):
            for key in ["domain", "intent", "route", "category"]:
                value = routed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()

        if isinstance(routed, str) and routed.strip():
            return routed.strip().lower()

        if any(x in msg for x in ["stock", "trade", "trading", "ticker", "market", "aapl", "nvda", "tsla", "tesla", "msft", "amazon", "google"]):
            return "finance"

        if any(x in msg for x in ["portfolio", "allocation", "capital", "wealth"]):
            return "finance"

        if any(x in msg for x in ["war", "iran", "china", "oil", "middle east", "macro", "geopolit"]):
            return "macro"

        if any(x in msg for x in ["business", "opportunity", "money", "monetize", "income", "revenue"]):
            return "strategy"

        if any(x in msg for x in ["task", "meeting", "agenda", "priority", "prioritize"]):
            return "ops"

        return "general"

    def _chat_fallback(self, message: str) -> str:
        result = self._call_first(
            self.conversation,
            [
                ("chat", (message,)),
                ("reply", (message, "general")),
                ("process", (message,)),
            ],
        )

        if isinstance(result, str) and result.strip():
            return result

        return "JARVIS is online, but the primary response engine is unavailable."

    def _normalize_text(self, result: Any, fallback: str = "No result returned.") -> str:
        if result is None:
            return fallback

        if isinstance(result, str) and result.strip():
            return result

        if isinstance(result, dict):
            for key in ["summary", "message", "response", "thesis", "details", "narrative"]:
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return str(result)

        return str(result)

    def respond(self, message: str) -> Dict[str, Any]:
        domain = self.detect_domain(message)

        # 1) Agent orchestrator first if available
        orchestrated = self._call_first(
            self.agent_orchestrator,
            [
                ("execute", (message, domain)),
                ("execute", (message,)),
                ("deliberate", (message, domain)),
                ("deliberate", (message,)),
                ("route", (domain,)),
            ],
        )

        if orchestrated is not None:
            return {
                "type": domain,
                "summary": self._normalize_text(orchestrated, fallback="Orchestrator returned no summary."),
                "details": orchestrated,
                "action": "Review and execute the recommended next step.",
                "confidence": 0.83,
                "source": "agent_orchestrator_pro",
            }

        # 2) Domain-specific fallbacks
        if domain == "finance":
            result = self.trader(message)
            return {
                "type": "finance",
                "summary": result.get("summary", "Financial analysis completed."),
                "details": result,
                "action": result.get("trade_plan", {}).get("action", "Review setup"),
                "confidence": 0.82 if result.get("traffic_light") in ["green", "blue"] else 0.68,
                "source": result.get("source", "finance_fallback"),
            }

        if domain == "macro":
            result = self._call_first(
                self.geopolitical,
                [
                    ("analyze", (message,)),
                    ("run", (message,)),
                    ("process", (message,)),
                    ("brief", (message,)),
                ],
            )
            return {
                "type": "macro",
                "summary": self._normalize_text(result, fallback=self._chat_fallback(message)),
                "details": result if result is not None else {},
                "action": "Monitor risk and update positioning.",
                "confidence": 0.77,
                "source": "geopolitical_intelligence_engine" if result is not None else "conversation_fallback",
            }

        if domain == "strategy":
            result = self._call_first(
                self.global_opportunity,
                [
                    ("analyze", (message,)),
                    ("run", (message,)),
                    ("process", (message,)),
                    ("scan", (message,)),
                ],
            )
            return {
                "type": "strategy",
                "summary": self._normalize_text(result, fallback=self._chat_fallback(message)),
                "details": result if result is not None else {},
                "action": "Select one opportunity and define execution owner.",
                "confidence": 0.79,
                "source": "global_opportunity_radar_pro" if result is not None else "conversation_fallback",
            }

        if domain == "ops":
            result = self._call_first(
                self.executive_briefing,
                [
                    ("analyze", (message,)),
                    ("run", (message,)),
                    ("process", (message,)),
                    ("brief", (message,)),
                ],
            )
            return {
                "type": "ops",
                "summary": self._normalize_text(result, fallback=self._chat_fallback(message)),
                "details": result if result is not None else {},
                "action": "Turn this into a concrete task or decision.",
                "confidence": 0.75,
                "source": "executive_briefing_engine" if result is not None else "conversation_fallback",
            }

        # 3) General fallback
        text = self._chat_fallback(message)
        return {
            "type": "general",
            "summary": text,
            "details": {"raw": text},
            "action": "Continue the conversation or ask for a specific analysis.",
            "confidence": 0.72,
            "source": "conversation_engine",
        }

    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        raw = (symbol_or_prompt or "").strip() or "AAPL"

        trader_result = self._call_first(
            self.trader_alpha,
            [
                ("analyze", (raw,)),
                ("run", (raw,)),
                ("process", (raw,)),
                ("generate_trade_plan", (raw,)),
                ("get_trade_setup", (raw,)),
            ],
        )

        if trader_result is not None:
            return self._normalize_trader_output(raw, trader_result, "trader_alpha_engine")

        market_result = self._call_first(
            self.market_intelligence,
            [
                ("analyze", (raw,)),
                ("run", (raw,)),
                ("process", (raw,)),
                ("get_market_view", (raw,)),
            ],
        )

        if market_result is not None:
            return self._normalize_trader_output(raw, market_result, "market_intelligence_engine")

        return {
            "symbol": raw.upper(),
            "setup_score": None,
            "traffic_light": "red",
            "technicals": {"price": None},
            "trade_plan": {
                "action": "NO TRADE",
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

    def _normalize_trader_output(self, raw: str, result: Any, source: str) -> Dict[str, Any]:
        if isinstance(result, dict):
            out = dict(result)
            out.setdefault("symbol", raw.upper())
            out.setdefault("setup_score", out.get("score"))
            out.setdefault("traffic_light", out.get("traffic_light", "orange"))
            out.setdefault("technicals", {"price": out.get("price")})
            out.setdefault(
                "trade_plan",
                {
                    "action": out.get("action", "REVIEW"),
                    "entry_zone": out.get("entry_zone", []),
                    "stop_loss": out.get("stop_loss", "-"),
                    "target_1": out.get("target_1", "-"),
                    "target_2": out.get("target_2", "-"),
                    "risk_reward_estimate": out.get("risk_reward_estimate", "-"),
                },
            )
            if "narrative" not in out:
                summary = out.get("summary") or out.get("message") or "No narrative."
                out["narrative"] = [summary]
            out.setdefault("summary", self._normalize_text(out, fallback="Trade analysis completed."))
            out.setdefault("source", source)
            return out

        if isinstance(result, str):
            return {
                "symbol": raw.upper(),
                "setup_score": None,
                "traffic_light": "orange",
                "technicals": {"price": None},
                "trade_plan": {
                    "action": "REVIEW",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-",
                },
                "narrative": [result],
                "summary": result,
                "source": source,
            }

        return {
            "symbol": raw.upper(),
            "setup_score": None,
            "traffic_light": "red",
            "technicals": {"price": None},
            "trade_plan": {
                "action": "NO TRADE",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "narrative": ["Unsupported trader output."],
            "summary": "Unsupported trader output.",
            "source": source,
        }
