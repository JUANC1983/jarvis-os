from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, Optional

try:
    import yfinance as yf
except Exception:
    yf = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class ProductBrain:
    """
    Presentation-safe product brain.

    Principles:
    - Do not break current core
    - Reuse current engines when they work
    - Fallback cleanly when one engine is incompatible
    - Always return dashboard-compatible payloads
    """

    def __init__(self) -> None:
        self.boot_events = []
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        self.client = None
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key and OpenAI is not None:
            try:
                self.client = OpenAI(api_key=api_key)
                self.boot_events.append("loaded openai client")
            except Exception as e:
                self.boot_events.append(f"failed openai client: {e}")

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
            "model": self.model,
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
                "yfinance": yf is not None,
                "openai": self.client is not None,
            },
        }

    def _normalize_text(self, result: Any, fallback: str = "No result returned.") -> str:
        if result is None:
            return fallback

        if isinstance(result, str) and result.strip():
            return result.strip()

        if isinstance(result, dict):
            for key in ["summary", "message", "response", "reply", "thesis", "details", "narrative", "consensus"]:
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return str(result)

        return str(result)

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
            return result.strip()

        if self.client is not None:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are JARVIS, an elite executive AI system. "
                                "Be concise, intelligent, calm and useful. "
                                "Focus on money, execution, clarity and risk."
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    temperature=0.4,
                )
                text = response.choices[0].message.content or ""
                if text.strip():
                    return text.strip()
            except Exception:
                pass

        return "JARVIS is online, but the primary response engine is unavailable."

    def detect_domain(self, message: str) -> str:
        msg = (message or "").lower()

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

        if any(x in msg for x in ["stock", "trade", "trading", "ticker", "market", "aapl", "nvda", "tsla", "tesla", "msft", "amazon", "amzn", "google", "googl", "meta"]):
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

    def _result_has_error(self, result: Any) -> bool:
        if result is None:
            return True

        if isinstance(result, dict):
            if result.get("error"):
                return True
            inner = result.get("result")
            if isinstance(inner, dict) and inner.get("error"):
                return True

        text = str(result).lower()
        return "no compatible method found" in text or "unavailable" in text

    def _extract_symbol(self, raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return "AAPL"

        aliases = {
            "tesla": "TSLA",
            "nvidia": "NVDA",
            "apple": "AAPL",
            "microsoft": "MSFT",
            "amazon": "AMZN",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "meta": "META",
        }

        lower = text.lower()
        for name, symbol in aliases.items():
            if name in lower:
                return symbol

        match = re.search(r"\b[A-Z]{1,5}\b", text.upper())
        if match:
            return match.group(0)

        cleaned = re.sub(r"[^A-Za-z]", "", text).upper()
        return cleaned[:5] if cleaned else "AAPL"

    def _fetch_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        if yf is None:
            return {"ok": False, "error": "yfinance not installed"}

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d", auto_adjust=False)

            if hist is None or hist.empty or len(hist) < 30:
                return {"ok": False, "error": f"No history returned for {symbol}"}

            close = hist["Close"].dropna()
            volume = hist["Volume"].dropna()

            price = float(close.iloc[-1])
            ma20 = float(close.tail(20).mean())
            ma50 = float(close.tail(50).mean()) if len(close) >= 50 else float(close.mean())
            high20 = float(close.tail(20).max())
            low20 = float(close.tail(20).min())
            ret5 = ((price / float(close.iloc[-6])) - 1.0) * 100 if len(close) >= 6 else 0.0
            ret20 = ((price / float(close.iloc[-21])) - 1.0) * 100 if len(close) >= 21 else 0.0
            avg_vol20 = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())

            score = 0
            if price > ma20:
                score += 2
            if ma20 > ma50:
                score += 2
            if ret5 > 0:
                score += 1
            if ret20 > 0:
                score += 2
            if price >= high20 * 0.98:
                score += 1
            if price <= low20 * 1.02:
                score -= 1

            if score >= 7:
                light = "blue"
                action = "BUY STRENGTH"
            elif score >= 5:
                light = "green"
                action = "BUY / ACCUMULATE"
            elif score >= 3:
                light = "orange"
                action = "WAIT / REVIEW"
            else:
                light = "red"
                action = "NO TRADE"

            entry_low = round(max(ma20, price * 0.985), 2)
            entry_high = round(price * 1.005, 2)
            stop_loss = round(min(ma20 * 0.97, price * 0.95), 2)
            target_1 = round(price * 1.04, 2)
            target_2 = round(price * 1.08, 2)

            rr = "-"
            risk = price - stop_loss
            reward = target_1 - price
            if risk > 0:
                rr = round(reward / risk, 2)

            summary = (
                f"{symbol} trades at {price:.2f}. "
                f"Short-term structure is {'constructive' if score >= 5 else 'mixed' if score >= 3 else 'weak'}, "
                f"with MA20 at {ma20:.2f} and MA50 at {ma50:.2f}."
            )

            narrative = [
                summary,
                f"5-day return: {ret5:.2f}%. 20-day return: {ret20:.2f}%.",
                f"20-day range: {low20:.2f} to {high20:.2f}.",
                f"Average 20-day volume: {avg_vol20:,.0f}.",
            ]

            return {
                "ok": True,
                "symbol": symbol,
                "setup_score": score,
                "traffic_light": light,
                "technicals": {
                    "price": round(price, 2),
                    "ma20": round(ma20, 2),
                    "ma50": round(ma50, 2),
                    "high20": round(high20, 2),
                    "low20": round(low20, 2),
                    "ret5": round(ret5, 2),
                    "ret20": round(ret20, 2),
                    "avg_vol20": round(avg_vol20, 0),
                },
                "trade_plan": {
                    "action": action,
                    "entry_zone": [entry_low, entry_high],
                    "stop_loss": stop_loss,
                    "target_1": target_1,
                    "target_2": target_2,
                    "risk_reward_estimate": rr,
                },
                "narrative": narrative,
                "summary": summary,
                "source": "yfinance_fallback",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _normalize_trader_output(self, raw: str, result: Any, source: str) -> Dict[str, Any]:
        if isinstance(result, dict):
            out = dict(result)
            out.setdefault("symbol", self._extract_symbol(raw))
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
                "symbol": self._extract_symbol(raw),
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
            "symbol": self._extract_symbol(raw),
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

    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        raw = (symbol_or_prompt or "").strip() or "AAPL"
        symbol = self._extract_symbol(raw)

        trader_result = self._call_first(
            self.trader_alpha,
            [
                ("analyze", (symbol,)),
                ("run", (symbol,)),
                ("process", (symbol,)),
                ("generate_trade_plan", (symbol,)),
                ("get_trade_setup", (symbol,)),
            ],
        )

        if trader_result is not None and not self._result_has_error(trader_result):
            return self._normalize_trader_output(symbol, trader_result, "trader_alpha_engine")

        market_result = self._call_first(
            self.market_intelligence,
            [
                ("analyze", (symbol,)),
                ("run", (symbol,)),
                ("process", (symbol,)),
                ("get_market_view", (symbol,)),
            ],
        )

        if market_result is not None and not self._result_has_error(market_result):
            return self._normalize_trader_output(symbol, market_result, "market_intelligence_engine")

        snapshot = self._fetch_market_snapshot(symbol)
        if snapshot.get("ok"):
            return snapshot

        return {
            "symbol": symbol,
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
            "narrative": [snapshot.get("error", "Trader engines unavailable.")],
            "summary": snapshot.get("error", "Trader engines unavailable."),
            "source": "fallback",
        }

    def respond(self, message: str) -> Dict[str, Any]:
        domain = self.detect_domain(message)

        if domain == "finance":
            trade = self.trader(message)
            summary = trade.get("summary", "Financial analysis completed.")
            return {
                "type": "finance",
                "reply": summary,
                "summary": summary,
                "details": trade,
                "action": trade.get("trade_plan", {}).get("action", "Review setup"),
                "confidence": 0.84 if trade.get("traffic_light") in ["green", "blue"] else 0.7,
                "source": trade.get("source", "finance"),
            }

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

        if orchestrated is not None and not self._result_has_error(orchestrated):
            summary = self._normalize_text(orchestrated, fallback="Analysis completed.")
            return {
                "type": domain,
                "reply": summary,
                "summary": summary,
                "details": orchestrated,
                "action": "Review and execute the recommended next step.",
                "confidence": 0.83,
                "source": "agent_orchestrator_pro",
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
            summary = self._normalize_text(result, fallback=self._chat_fallback(message))
            return {
                "type": "macro",
                "reply": summary,
                "summary": summary,
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
            summary = self._normalize_text(result, fallback=self._chat_fallback(message))
            return {
                "type": "strategy",
                "reply": summary,
                "summary": summary,
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
            summary = self._normalize_text(result, fallback=self._chat_fallback(message))
            return {
                "type": "ops",
                "reply": summary,
                "summary": summary,
                "details": result if result is not None else {},
                "action": "Turn this into a concrete task or decision.",
                "confidence": 0.75,
                "source": "executive_briefing_engine" if result is not None else "conversation_fallback",
            }

        text = self._chat_fallback(message)
        return {
            "type": "general",
            "reply": text,
            "summary": text,
            "details": {"raw": text},
            "action": "Continue the conversation or ask for a specific analysis.",
            "confidence": 0.72,
            "source": "conversation_engine",
        }
