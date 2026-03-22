from __future__ import annotations

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

        self.agent_orchestrator = self._safe_instance("core.agent_orchestrator_pro", "AgentOrchestratorPro")
        self.conversation = self._safe_instance("core.conversation_engine", "ConversationEngine")
        self.trader_alpha = self._safe_instance("core.trader_alpha_engine", "TraderAlphaEngine")
        self.market_intelligence = self._safe_instance("core.market_intelligence_engine", "MarketIntelligenceEngine")

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
                "agent_orchestrator": self.agent_orchestrator is not None,
                "conversation": self.conversation is not None,
                "trader_alpha": self.trader_alpha is not None,
                "market_intelligence": self.market_intelligence is not None,
                "yfinance": yf is not None,
                "openai": self.client is not None,
            },
        }

    def _normalize_text(self, value: Any, fallback: str = "No result.") -> str:
        if value is None:
            return fallback

        if isinstance(value, str) and value.strip():
            return value.strip()

        if isinstance(value, dict):
            for key in ["reply", "summary", "message", "response", "consensus", "result"]:
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return str(value)

        return str(value)

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
            "asml": "ASML",
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

    def _chat_fallback(self, message: str) -> str:
        msg = (message or "").strip()
        low = msg.lower()

        if low in ["hola", "hello", "hi", "hey"]:
            return "Hola. Soy JARVIS. Estoy listo para ayudarte con estrategia, trading, prioridades y ejecución."

        if "como te llamas" in low or "quien eres" in low or "who are you" in low or "your name" in low:
            return "Soy JARVIS, tu sistema operativo estratégico de AI para decisiones, trading y ejecución."

        conv_result = self._call_first(
            self.conversation,
            [
                ("chat", (message,)),
                ("reply", (message, "general")),
                ("process", (message,)),
            ],
        )

        if isinstance(conv_result, str) and conv_result.strip():
            cleaned = conv_result.strip()
            if "executed with primary agent" not in cleaned.lower():
                return cleaned

        if self.client is not None:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are JARVIS, an elite executive AI assistant. "
                                "Reply in the same language as the user. "
                                "Be clear, human, concise, strategic and useful. "
                                "Do not mention internal agents, routers or execution traces."
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

        return "JARVIS está online. Puedo ayudarte con trading, prioridades, estrategia y ejecución."

    def detect_domain(self, message: str) -> str:
        msg = (message or "").lower()

        if any(x in msg for x in ["stock", "ticker", "trade", "trading", "nvda", "aapl", "tsla", "asml", "msft", "amzn", "googl", "meta"]):
            return "finance"

        if any(x in msg for x in ["money", "dinero", "opportunity", "oportunidad", "strategy", "estrategia", "business"]):
            return "strategy"

        return "general"

    def _fetch_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        if yf is None:
            return {"ok": False, "error": "Market data provider unavailable."}

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d", auto_adjust=False)

            if hist is None or hist.empty or len(hist) < 30:
                return {"ok": False, "error": f"No market history available for {symbol}."}

            close = hist["Close"].dropna()
            volume = hist["Volume"].dropna()

            price = float(close.iloc[-1])
            ma20 = float(close.tail(20).mean())
            ma50 = float(close.tail(50).mean()) if len(close) >= 50 else float(close.mean())
            high20 = float(close.tail(20).max())
            low20 = float(close.tail(20).min())
            ret20 = ((price / float(close.iloc[-21])) - 1.0) * 100 if len(close) >= 21 else 0.0

            score = 50
            if price > ma20:
                score += 10
            if ma20 > ma50:
                score += 10
            if ret20 > 0:
                score += 10
            if price >= high20 * 0.97:
                score += 5
            if price <= low20 * 1.03:
                score -= 10
            score = max(10, min(95, score))

            if score >= 85:
                traffic_light = "green"
                action = "Buy opportunity"
                explanation = "La tendencia es fuerte y el contexto acompaña. Tiene sentido entrar por tramos."
            elif score >= 70:
                traffic_light = "yellow"
                action = "Wait"
                explanation = "La estructura es aceptable, pero el punto de entrada no es ideal todavía."
            elif score >= 55:
                traffic_light = "yellow"
                action = "Wait"
                explanation = "Hay señales mixtas. Mejor esperar confirmación antes de comprar."
            else:
                traffic_light = "red"
                action = "Avoid"
                explanation = "El riesgo no compensa. No es una entrada limpia ahora."

            entry_low = round(max(price * 0.98, low20 * 1.01), 2)
            entry_high = round(min(price * 1.02, high20 * 0.99), 2)

            if entry_low > entry_high:
                entry_low = round(price * 0.99, 2)
                entry_high = round(price * 1.01, 2)

            stop_loss = round(entry_low * 0.97, 2)
            target_1 = round(price * 1.03, 2)
            target_2 = round(price * 1.06, 2)

            risk = max(entry_high - stop_loss, 0.01)
            reward = max(target_1 - entry_high, 0.01)
            rr = round(reward / risk, 2)

            if rr < 1.0 and traffic_light != "red":
                traffic_light = "yellow"
                action = "Wait"
                explanation = "El riesgo-beneficio todavía no es suficientemente atractivo para entrar ya."

            trend = "alcista" if price > ma20 > ma50 else "mixta" if price > ma20 else "débil"

            return {
                "ok": True,
                "symbol": symbol,
                "setup_score": score,
                "traffic_light": traffic_light,
                "price_now": round(price, 2),
                "trade_plan": {
                    "action": action,
                    "entry_zone": [entry_low, entry_high],
                    "stop_loss": stop_loss,
                    "target_1": target_1,
                    "target_2": target_2,
                    "risk_reward_estimate": rr,
                },
                "insight_lines": [
                    f"{symbol} está en una estructura {trend}.",
                    explanation,
                    f"Precio actual: {round(price, 2)}.",
                ],
                "summary": f"{symbol}: {action}. {explanation}",
                "friendly_recommendation": explanation,
                "source": "market_fallback",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        symbol = self._extract_symbol(symbol_or_prompt)
        snap = self._fetch_market_snapshot(symbol)

        if snap.get("ok"):
            return snap

        return {
            "symbol": symbol,
            "setup_score": 0,
            "traffic_light": "red",
            "price_now": None,
            "trade_plan": {
                "action": "Avoid",
                "entry_zone": ["-", "-"],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "insight_lines": ["No pude obtener datos de mercado confiables ahora."],
            "summary": "No pude obtener datos de mercado confiables ahora.",
            "friendly_recommendation": "Revisa de nuevo en unos minutos.",
            "source": "fallback",
        }

    def auto_brief(self) -> Dict[str, Any]:
        tickers = ["NVDA", "AAPL", "MSFT", "ASML"]
        analyses = [self.trader(t) for t in tickers]

        sorted_items = sorted(analyses, key=lambda x: x.get("setup_score", 0), reverse=True)
        best = sorted_items[0] if sorted_items else None

        if not best:
            return {
                "reply": "No hay análisis disponible en este momento.",
                "summary": "No hay análisis disponible en este momento.",
                "items": [],
            }

        return {
            "reply": (
                f"Auto JARVIS completado. La mejor lectura actual es {best.get('symbol')} "
                f"con score {best.get('setup_score')}. "
                f"Acción sugerida: {best.get('trade_plan', {}).get('action', 'Wait')}."
            ),
            "summary": (
                f"Mejor oportunidad observada: {best.get('symbol')} "
                f"con score {best.get('setup_score')}."
            ),
            "items": sorted_items,
        }

    def respond(self, message: str) -> Dict[str, Any]:
        domain = self.detect_domain(message)

        if domain == "finance":
            trade = self.trader(message)
            return {
                "type": "finance",
                "reply": trade.get("summary", "Análisis completado."),
                "summary": trade.get("summary", "Análisis completado."),
                "details": trade,
                "action": trade.get("trade_plan", {}).get("action", "Wait"),
                "confidence": 0.82,
                "source": trade.get("source", "market_fallback"),
            }

        text = self._chat_fallback(message)
        return {
            "type": "general",
            "reply": text,
            "summary": text,
            "details": {"text": text},
            "action": "Continúa la conversación o pide análisis de una acción.",
            "confidence": 0.74,
            "source": "conversation_layer",
        }
