from __future__ import annotations

from typing import Any, Dict, List

from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.opportunity_master_engine import OpportunityMasterEngine


class ProductBrain:
    def __init__(self) -> None:
        self.orchestrator = AgentOrchestratorPro()
        self.opportunity_engine = OpportunityMasterEngine()

        self.finance_keywords = [
            "acción", "acciones", "stock", "stocks", "bolsa", "trader", "trading",
            "invertir", "inversión", "inversion", "mercado", "ticker", "precio",
            "oro", "gold", "nasdaq", "sp500", "s&p", "semana", "oportunidad",
            "oportunidades", "buy", "sell", "entry", "setup", "riesgo",
            "apple", "tesla", "google", "amazon", "nvidia", "meta", "amd",
            "msft", "aapl", "tsla", "nvda", "amzn", "googl", "asml", "coin",
            "pltr", "gld", "msft", "mercados"
        ]

    def health(self) -> dict:
        return {
            "available": True,
            "boot_errors": [],
            "orchestrator_available": True,
        }

    def respond(self, message: str) -> Dict:
        return self.chat(message)

    def _is_finance_query(self, message: str) -> bool:
        low = message.lower()
        return any(word in low for word in self.finance_keywords)

    def _extract_symbol_from_text(self, message: str) -> str | None:
        tokens = (
            message.replace(",", " ")
            .replace(".", " ")
            .replace("?", " ")
            .replace("¿", " ")
            .replace("!", " ")
            .replace(":", " ")
            .replace(";", " ")
            .split()
        )

        for token in tokens:
            candidate = self.opportunity_engine.resolve_symbol(token)
            if 1 <= len(candidate) <= 6 and candidate.isupper():
                if candidate in {
                    "AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "GOOG", "META", "AMZN", "TSLA",
                    "NFLX", "PLTR", "COIN", "ASML", "GLD", "SLV", "SMH", "QQQ", "SPY"
                }:
                    return candidate

        text = message.lower()

        mapping = {
            "apple": "AAPL",
            "microsoft": "MSFT",
            "nvidia": "NVDA",
            "amd": "AMD",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "amazon": "AMZN",
            "tesla": "TSLA",
            "netflix": "NFLX",
            "palantir": "PLTR",
            "coinbase": "COIN",
            "asml": "ASML",
            "oro": "GLD",
            "gold": "GLD",
        }

        for key, value in mapping.items():
            if key in text:
                return value

        return None

    def _friendly_market_reply(self, items: List[Dict]) -> str:
        if not items:
            return "No veo una oportunidad clara ahora mismo."

        best = items[0]
        symbol = best.get("symbol", "-")
        score = best.get("setup_score", "-")
        action = best.get("trade_plan", {}).get("action", best.get("traffic_light", "WAIT"))
        price = best.get("price_now", best.get("price"))
        reason = best.get("friendly_recommendation", "")
        insights = best.get("insight_lines", [])

        extra = insights[0] if insights else ""
        return f"Mi mejor idea ahora es {symbol}. Score {score}. Precio {price}. Acción sugerida: {action}. {reason} {extra}".strip()

    def chat(self, message: str) -> dict:
    message_lower = message.lower().strip()

    # =========================
    # 1. GREETING (HUMANO)
    # =========================
    if message_lower in ["hola", "hola jarvis", "hey", "hi"]:
        return {
            "type": "chat",
            "reply": "Hola Juan. ¿Qué necesitas hoy?",
            "summary": "Saludo inicial",
            "details": {},
            "action": "",
            "confidence": 1.0,
            "source": "brain_simple"
        }

    # =========================
    # 2. INTENCIÓN TRADING
    # =========================
    if any(word in message_lower for word in ["stock", "accion", "trade", "ticker"]):
        return {
            "type": "chat",
            "reply": "Dime el símbolo (ej: AAPL, TSLA) y te doy el análisis.",
            "summary": "Solicitud de análisis de activo",
            "details": {},
            "action": "ask_symbol",
            "confidence": 0.9,
            "source": "brain_simple"
        }

    # =========================
    # 3. INTENCIÓN RECOMENDACIONES
    # =========================
    if "oportunidad" in message_lower or "recomend" in message_lower:
        try:
            recs = self.recommendations()
            items = recs.get("items", [])[:3]

            if not items:
                return {
                    "type": "chat",
                    "reply": "Ahora mismo no veo setups claros.",
                    "summary": "Sin oportunidades",
                    "details": {},
                    "action": "",
                    "confidence": 0.7,
                    "source": "brain_simple"
                }

            top = ", ".join([x["symbol"] for x in items])

            return {
                "type": "chat",
                "reply": f"Las mejores oportunidades ahora: {top}",
                "summary": "Top oportunidades",
                "details": items,
                "action": "",
                "confidence": 0.9,
                "source": "brain_simple"
            }

        except Exception as e:
            return {
                "type": "error",
                "reply": f"No pude obtener oportunidades: {e}",
                "summary": "Error recomendaciones",
                "details": {},
                "action": "",
                "confidence": 0.2,
                "source": "brain_simple"
            }

    # =========================
    # 4. FALLBACK (SIN ORCHESTRATOR)
    # =========================
    return {
        "type": "chat",
        "reply": "Dime qué necesitas: trading, tareas o algo específico.",
        "summary": "Fallback simple",
        "details": {},
        "action": "",
        "confidence": 0.6,
        "source": "brain_simple"
    }                    "type": "chat",
                    "summary": "Escríbeme algo concreto y te respondo con claridad.",
                    "reply": "Escríbeme algo concreto y te respondo con claridad.",
                    "details": {},
                    "action": "",
                    "confidence": 0.4,
                    "source": "product_brain",
                }

            if self._is_finance_query(text):
                symbol = self._extract_symbol_from_text(text)

                if symbol:
                    data = self.trader(symbol)
                    reply = self._friendly_market_reply([data])
                    return {
                        "type": "trade_idea",
                        "summary": reply,
                        "reply": reply,
                        "details": data,
                        "action": data.get("trade_plan", {}).get("action", ""),
                        "confidence": 0.9,
                        "source": "opportunity_master",
                    }

                items = self.recommendations().get("items", [])
                reply = self._friendly_market_reply(items)

                return {
                    "type": "market_brief",
                    "summary": reply,
                    "reply": reply,
                    "details": {"items": items[:5]},
                    "action": items[0].get("trade_plan", {}).get("action", "") if items else "",
                    "confidence": 0.88,
                    "source": "opportunity_master",
                }

            result = self.orchestrator.execute(text, domain="general")
            raw = result.get("result")

            reply = ""
            if isinstance(raw, dict):
                reply = (
                    raw.get("reply")
                    or raw.get("summary")
                    or raw.get("consensus")
                    or raw.get("result")
                    or result.get("summary")
                    or "Entendido."
                )
            elif isinstance(raw, list):
                reply = "\n".join([str(x) for x in raw[:3]])
            else:
                reply = str(raw or result.get("summary") or "Entendido.")

            return {
                "type": "chat",
                "summary": reply,
                "reply": reply,
                "details": raw if isinstance(raw, dict) else {},
                "action": "",
                "confidence": 0.82,
                "source": "orchestrator",
            }

        except Exception as e:
            return {
                "type": "error",
                "summary": f"Error en chat: {e}",
                "reply": f"Error en chat: {e}",
                "details": {},
                "action": "",
                "confidence": 0.1,
                "source": "product_brain",
            }

    def trader(self, symbol_or_name: str) -> Dict:
        data = self.opportunity_engine.analyze_symbol(symbol_or_name)

        data.setdefault("symbol", self.opportunity_engine.resolve_symbol(symbol_or_name))
        data.setdefault("price", data.get("price_now"))
        data.setdefault("price_now", data.get("price"))
        data.setdefault("setup_score", 0)
        data.setdefault("traffic_light", "red")
        data.setdefault("trade_plan", {
            "action": "AVOID",
            "entry_zone": [],
            "stop_loss": "-",
            "target_1": "-",
            "target_2": "-",
            "risk_reward_estimate": "-",
        })
        data.setdefault("insight_lines", [data.get("summary", "Sin insight disponible.")])
        data.setdefault("friendly_recommendation", "No hay suficiente ventaja ahora mismo.")

        return data

    def recommendations(self) -> Dict:
        items = self.opportunity_engine.get_top_opportunities(limit=8, force_refresh=False)
        return {"items": items}

