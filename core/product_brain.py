from __future__ import annotations

from typing import Any, Dict, List, Optional
import math
import traceback

import numpy as np
import yfinance as yf

try:
    from core.agent_orchestrator_pro import AgentOrchestratorPro
except Exception:
    AgentOrchestratorPro = None


class ProductBrain:
    def __init__(self) -> None:
        self.orchestrator = None
        self.boot_errors: List[str] = []

        if AgentOrchestratorPro is not None:
            try:
                self.orchestrator = AgentOrchestratorPro()
            except Exception as e:
                self.boot_errors.append(f"orchestrator_init: {e}")

        self.name_to_symbol = {
            "tesla": "TSLA",
            "tsla": "TSLA",
            "apple": "AAPL",
            "aapl": "AAPL",
            "microsoft": "MSFT",
            "msft": "MSFT",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "googl": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "amazon": "AMZN",
            "amzn": "AMZN",
            "nvidia": "NVDA",
            "nvda": "NVDA",
            "asml": "ASML",
            "netflix": "NFLX",
            "nflx": "NFLX",
            "broadcom": "AVGO",
            "avgo": "AVGO",
            "oracle": "ORCL",
            "orcl": "ORCL",
            "palantir": "PLTR",
            "pltr": "PLTR",
            "amd": "AMD",
            "snowflake": "SNOW",
            "snow": "SNOW",
            "coinbase": "COIN",
            "coin": "COIN",
            "gold": "GLD",
            "oro": "GLD",
            "silver": "SLV",
            "plata": "SLV",
            "spy": "SPY",
            "qqq": "QQQ",
        }

        self.recommendation_universe = [
            "NVDA", "MSFT", "META", "GOOGL", "AMZN", "AAPL", "AVGO", "ORCL",
            "PLTR", "AMD", "NFLX", "ASML", "SNOW", "COIN", "SPY", "QQQ", "GLD"
        ]

    def health(self) -> Dict[str, Any]:
        return {
            "available": True,
            "boot_errors": self.boot_errors,
            "orchestrator_available": self.orchestrator is not None,
        }

    def respond(self, message: str) -> Dict[str, Any]:
        return self.chat(message)

    def chat(self, message: str) -> Dict[str, Any]:
        text = (message or "").strip()
        lower = text.lower()

        if not text:
            return self._chat_response("Escríbeme algo y te respondo claro, útil y directo.")

        if lower in {"hola", "hola jarvis", "buenas", "hello", "hi"}:
            return self._chat_response("Hola. Estoy listo. Puedo ayudarte con inversión, negocio, legal, médico, productividad, golf y estrategia.")

        if self._is_finance_query(lower):
            recs = self.recommendations().get("items", [])
            if not recs:
                return self._chat_response("No pude generar recomendaciones ahora mismo. Intenta en unos segundos.")

            top = recs[:3]
            lines = []
            for item in top:
                lines.append(
                    f"{item['symbol']}: {item['friendly_recommendation']} "
                    f"Precio {item.get('price_now', '-')}, score {item.get('setup_score', '-')}"
                )

            summary = "Estas son mis mejores ideas ahora mismo:\n- " + "\n- ".join(lines)
            return {
                "type": "finance",
                "reply": summary,
                "summary": summary,
                "details": {"top_ideas": top},
                "action": "Revisar primero las 3 ideas con mejor score.",
                "confidence": 0.86,
                "source": "product_brain_finance",
            }

        domain = self._infer_domain(lower)
        if self.orchestrator is not None and domain != "general":
            try:
                result = self.orchestrator.execute(text, domain)
                natural = self._naturalize_orchestrator_output(text, domain, result)
                return {
                    "type": domain,
                    "reply": natural,
                    "summary": natural,
                    "details": result,
                    "action": "",
                    "confidence": 0.78,
                    "source": "agent_orchestrator_pro",
                }
            except Exception as e:
                self.boot_errors.append(f"orchestrator_chat: {e}")

        return self._chat_response(
            "Entendido. Puedo ayudarte en inversión, negocio, tareas, salud, legal, golf y estrategia. Hazme una pregunta concreta y te responderé accionable."
        )

    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:
        symbol = self._resolve_symbol(symbol_or_prompt)
        analysis = self._analyze_symbol(symbol)

        if analysis.get("error"):
            return {
                "symbol": symbol,
                "price": None,
                "price_now": None,
                "setup_score": None,
                "traffic_light": "red",
                "trade_plan": {
                    "action": "AVOID",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-",
                },
                "insight_lines": [analysis["error"]],
                "summary": analysis["error"],
                "friendly_recommendation": "No pude analizar este activo ahora mismo.",
                "source": "product_brain_trader",
            }

        return analysis

    def recommendations(self) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []

        for symbol in self.recommendation_universe:
            try:
                item = self._analyze_symbol(symbol, compact=True)
                if item.get("error"):
                    continue
                items.append(item)
            except Exception:
                continue

        items = [x for x in items if x.get("setup_score") is not None]
        items.sort(key=lambda x: x["setup_score"], reverse=True)

        preferred = [x for x in items if x.get("traffic_light") in ("green", "blue", "yellow")]
        final_items = preferred[:6] if preferred else items[:6]

        return {"items": final_items}

    def _infer_domain(self, lower: str) -> str:
        if any(k in lower for k in ["acción", "acciones", "stock", "stocks", "invert", "mercado", "oro", "trading", "bolsa"]):
            return "finance"
        if any(k in lower for k in ["doctor", "médico", "medico", "salud", "síntoma", "sintoma", "enfermo"]):
            return "medical"
        if any(k in lower for k in ["contrato", "legal", "abogado", "demanda", "ley"]):
            return "legal"
        return "general"

    def _is_finance_query(self, lower: str) -> bool:
        keys = [
            "accion", "acciones", "stock", "stocks", "invert", "inversión", "inversion",
            "mercado", "trading", "bolsa", "oro", "comprar", "recomiendas", "recomiendame",
            "semana", "ticker", "precio"
        ]
        return any(k in lower for k in keys)

    def _chat_response(self, text: str) -> Dict[str, Any]:
        return {
            "type": "chat",
            "reply": text,
            "summary": text,
            "details": {},
            "action": "",
            "confidence": 0.9,
            "source": "product_brain",
        }

    def _naturalize_orchestrator_output(self, query: str, domain: str, result: Dict[str, Any]) -> str:
        if not isinstance(result, dict):
            return str(result)

        payload = result.get("result")

        if isinstance(payload, str) and payload.strip():
            return payload.strip()

        if isinstance(payload, dict):
            for key in ["summary", "reply", "consensus", "recommendation", "result"]:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

            opinions = payload.get("opinions")
            if isinstance(opinions, list) and opinions:
                clean = []
                for item in opinions[:3]:
                    if isinstance(item, dict):
                        agent = item.get("agent", "agent")
                        opinion = item.get("opinion", "")
                        if opinion:
                            clean.append(f"{agent}: {opinion}")
                if clean:
                    return "Resumen del consejo especializado:\n- " + "\n- ".join(clean)

        summary = result.get("summary")
        if isinstance(summary, str) and summary.strip():
            return f"Procesé tu consulta. {summary}"

        return "Procesé tu consulta, pero el agente no devolvió una respuesta final clara todavía."

    def _resolve_symbol(self, value: str) -> str:
        raw = (value or "").strip()
        lower = raw.lower()

        if lower in self.name_to_symbol:
            return self.name_to_symbol[lower]

        cleaned = "".join(ch for ch in raw.upper() if ch.isalnum())
        if cleaned in self.name_to_symbol.values():
            return cleaned

        return cleaned or "AAPL"

    def _analyze_symbol(self, symbol: str, compact: bool = False) -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo", interval="1d", auto_adjust=True)

            if hist is None or hist.empty or len(hist) < 60:
                return {"error": f"No pude obtener suficiente data para {symbol}."}

            close = hist["Close"].dropna()
            volume = hist["Volume"].fillna(0)

            price = float(close.iloc[-1])
            sma20 = float(close.tail(20).mean())
            sma50 = float(close.tail(50).mean())
            sma100 = float(close.tail(100).mean()) if len(close) >= 100 else sma50
            ret_5 = float((price / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
            ret_20 = float((price / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0
            vol_avg20 = float(volume.tail(20).mean()) if len(volume) >= 20 else 0.0
            vol_last = float(volume.iloc[-1]) if len(volume) else 0.0

            returns = close.pct_change().dropna()
            daily_vol = float(returns.tail(20).std() * math.sqrt(252) * 100) if len(returns) >= 20 else 0.0

            high_20 = float(close.tail(20).max())
            low_20 = float(close.tail(20).min())
            atr_proxy = max(price * 0.025, abs(high_20 - low_20) * 0.18)

            score = 50

            if price > sma20:
                score += 8
            else:
                score -= 6

            if sma20 > sma50:
                score += 10
            else:
                score -= 8

            if sma50 > sma100:
                score += 8
            else:
                score -= 6

            if ret_5 > 1.5:
                score += 8
            elif ret_5 < -1.5:
                score -= 8

            if ret_20 > 4:
                score += 10
            elif ret_20 < -4:
                score -= 10

            if vol_last > vol_avg20 * 1.1 and price > sma20:
                score += 6

            if daily_vol > 55:
                score -= 8
            elif daily_vol < 28:
                score += 4

            score = int(max(5, min(95, score)))

            if score >= 80:
                traffic = "green"
                action = "STRONG BUY"
                friendly = "Setup fuerte. Vale la pena revisar entrada hoy si confirma fuerza."
            elif score >= 68:
                traffic = "blue"
                action = "BUY"
                friendly = "Buena candidata. Tiene contexto favorable y merece seguimiento cercano."
            elif score >= 55:
                traffic = "yellow"
                action = "WAIT"
                friendly = "Interesante, pero todavía prefiero esperar una entrada más limpia."
            else:
                traffic = "red"
                action = "AVOID"
                friendly = "Ahora no es una entrada limpia. Riesgo alto frente al beneficio esperado."

            entry_low = round(max(low_20, price - atr_proxy * 0.35), 2)
            entry_high = round(min(high_20, price + atr_proxy * 0.35), 2)
            stop_loss = round(price - atr_proxy, 2)
            target_1 = round(price + atr_proxy * 1.2, 2)
            target_2 = round(price + atr_proxy * 2.0, 2)
            rr = round((target_1 - price) / max(0.01, price - stop_loss), 2)

            insights = []
            insights.append("Tendencia de corto plazo favorable." if price > sma20 else "Debilidad de corto plazo.")
            insights.append("Tendencia media positiva." if sma20 > sma50 else "La media de 20 días sigue débil frente a la de 50.")
            insights.append("Volumen acompañando." if vol_last > vol_avg20 else "Volumen neutral.")
            insights.append(f"Momentum 5d: {ret_5:.2f}% | Momentum 20d: {ret_20:.2f}%")

            payload = {
                "symbol": symbol,
                "price": round(price, 2),
                "price_now": round(price, 2),
                "setup_score": score,
                "traffic_light": traffic,
                "trade_plan": {
                    "action": action,
                    "entry_zone": [entry_low, entry_high],
                    "stop_loss": stop_loss,
                    "target_1": target_1,
                    "target_2": target_2,
                    "risk_reward_estimate": rr,
                },
                "insight_lines": insights[:4],
                "summary": f"{symbol} | precio {round(price,2)} | score {score} | acción {action}",
                "friendly_recommendation": friendly,
                "source": "product_brain_market",
            }

            if compact:
                return payload

            return payload

        except Exception as e:
            return {"error": f"Error analizando {symbol}: {e}"}
