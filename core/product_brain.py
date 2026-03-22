from __future__ import annotations

from typing import Any, Dict, List
import random

try:
    import requests
except Exception:
    requests = None

try:
    import yfinance as yf
except Exception:
    yf = None


class ProductBrain:
    def __init__(self) -> None:
        self.default_watchlist = ["NVDA", "AAPL", "MSFT", "ASML"]

    def health(self) -> Dict[str, Any]:
        return {
            "available": True,
            "source": "product_brain",
            "yfinance_installed": yf is not None,
            "requests_installed": requests is not None,
        }

    def chat(self, message: str, domain: str = "general") -> Dict[str, Any]:
        msg = (message or "").strip()
        if not msg:
            return {
                "type": "chat",
                "summary": "Escríbeme algo y te respondo claro y útil.",
                "details": {},
                "action": "",
                "confidence": 0.95,
                "source": "product_brain",
            }

        lower = msg.lower()

        if any(word in lower for word in ["oro", "gold"]):
            text = (
                "Oro sirve para proteger capital, no para crecer rápido. "
                "Tiene sentido si esperas inflación, crisis o quieres cobertura. "
                "Para una cartera personal, normalmente 5% a 15% es suficiente."
            )
            return self._chat_payload(text)

        if any(word in lower for word in ["guerra", "war", "conflicto"]):
            text = (
                "En escenarios de guerra o tensión geopolítica, normalmente ganan atención "
                "energía, defensa, oro y ciberseguridad. La clave no es comprar por miedo, "
                "sino esperar entradas limpias y controlar riesgo."
            )
            return self._chat_payload(text)

        if any(word in lower for word in ["acciones", "stocks", "invertir", "inversión", "inversion"]):
            text = (
                "Hoy no conviene comprar cualquier acción. Hay que priorizar calidad, tendencia y contexto. "
                "Puedo ayudarte mejor si me dices: horizonte, capital disponible y tolerancia al riesgo."
            )
            return self._chat_payload(text)

        if any(word in lower for word in ["negocio", "dinero", "hacer dinero", "oportunidad"]):
            text = (
                "Las oportunidades más rápidas hoy están en vender automatización con AI, "
                "chatbots de WhatsApp y servicios de eficiencia operativa a empresas. "
                "Eso suele monetizar más rápido que escribir contenido genérico."
            )
            return self._chat_payload(text)

        if any(word in lower for word in ["hola", "quién eres", "quien eres", "como te llamas", "cómo te llamas"]):
            text = (
                "Soy JARVIS. Tu sistema operativo estratégico. "
                "Puedo ayudarte a pensar, decidir, priorizar y analizar oportunidades con criterio."
            )
            return self._chat_payload(text)

        text = (
            "Entendido. Puedo ayudarte en estrategia, inversión, negocio, tareas y priorización. "
            "Hazme una pregunta más específica y te respondo con una recomendación accionable."
        )
        return self._chat_payload(text)

    def trader(self, symbol: str) -> Dict[str, Any]:
        clean_symbol = self._normalize_symbol(symbol)
        snapshot = self._fetch_market_snapshot(clean_symbol)

        if not snapshot.get("ok"):
            return {
                "symbol": clean_symbol,
                "setup_score": 40,
                "traffic_light": "red",
                "price_now": "--",
                "trade_plan": {
                    "action": "WAIT",
                    "entry_zone": ["-", "-"],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-",
                },
                "narrative": [
                    "No pude obtener precio confiable en este momento.",
                    "Reintenta en unos segundos o prueba otro ticker.",
                ],
                "summary": "Sin datos de precio por ahora.",
                "friendly_recommendation": "No ejecutar ninguna operación sin precio válido.",
                "source": "product_brain",
            }

        price = snapshot["price_now"]
        score = snapshot["setup_score"]
        light = snapshot["traffic_light"]

        if score >= 78:
            action = "BUY"
            friendly = "Setup fuerte. Solo entrar si el precio confirma y el riesgo está controlado."
        elif score >= 62:
            action = "WAIT"
            friendly = "Setup aceptable. Mejor esperar una entrada más limpia."
        else:
            action = "AVOID"
            friendly = "No hay ventaja clara ahora. Mejor no entrar."

        entry_low = round(price * 0.985, 2)
        entry_high = round(price * 1.01, 2)
        stop_loss = round(price * 0.965, 2)
        target_1 = round(price * 1.035, 2)
        target_2 = round(price * 1.065, 2)

        return {
            "symbol": clean_symbol,
            "setup_score": score,
            "traffic_light": light,
            "price_now": price,
            "trade_plan": {
                "action": action,
                "entry_zone": [entry_low, entry_high],
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "risk_reward_estimate": 1.6,
            },
            "narrative": [
                f"{clean_symbol} cotiza cerca de {price}.",
                friendly,
                "Nunca ejecutes una compra solo porque el activo se vea fuerte; espera timing y controla tamaño."
            ],
            "summary": friendly,
            "friendly_recommendation": friendly,
            "source": "product_brain",
        }

    def recommendations(self) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []

        for symbol in self.default_watchlist:
            result = self.trader(symbol)

            light = result.get("traffic_light", "red")
            label = self._light_label(light)

            items.append({
                "symbol": result.get("symbol", symbol),
                "setup_score": result.get("setup_score", 40),
                "traffic_light": light,
                "reason": f"{label}. {result.get('summary', 'Sin resumen.')}",
                "summary": result.get("summary", "Sin resumen."),
            })

        ranked = sorted(items, key=lambda x: x.get("setup_score", 0), reverse=True)

        return {"items": ranked, "source": "product_brain"}

    def _fetch_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        price = None

        if yf is not None:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo", interval="1d")
                if hist is not None and not hist.empty:
                    last_close = hist["Close"].dropna()
                    if len(last_close) > 0:
                        price = float(last_close.iloc[-1])
            except Exception:
                price = None

        if price is None and requests is not None:
            try:
                url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
                response = requests.get(url, timeout=8)
                data = response.json()
                result = data.get("quoteResponse", {}).get("result", [])
                if result:
                    raw = result[0].get("regularMarketPrice")
                    if raw is not None:
                        price = float(raw)
            except Exception:
                price = None

        if price is None:
            return {"ok": False, "error": "No price data"}

        base_score = 58

        if price >= 50:
            base_score += 4
        if price >= 100:
            base_score += 4
        if price >= 200:
            base_score += 3

        random_adjustment = random.randint(-8, 12)
        score = max(35, min(88, base_score + random_adjustment))

        if score >= 78:
            traffic_light = "green"
        elif score >= 62:
            traffic_light = "yellow"
        else:
            traffic_light = "red"

        return {
            "ok": True,
            "symbol": symbol,
            "price_now": round(price, 2),
            "setup_score": score,
            "traffic_light": traffic_light,
        }

    def _chat_payload(self, text: str) -> Dict[str, Any]:
        return {
            "type": "chat",
            "summary": text,
            "details": {},
            "action": "",
            "confidence": 0.9,
            "source": "product_brain",
        }

    def _normalize_symbol(self, symbol: str) -> str:
        value = (symbol or "AAPL").strip().upper()
        if not value:
            return "AAPL"

        aliases = {
            "GOOGLE": "GOOGL",
            "AMAZON": "AMZN",
            "TESLA": "TSLA",
            "APPLE": "AAPL",
            "MICROSOFT": "MSFT",
            "NVIDIA": "NVDA",
        }
        return aliases.get(value, value)

    def _light_label(self, light: str) -> str:
        mapping = {
            "green": "Verde",
            "yellow": "Stand by",
            "red": "Avoid",
        }
        return mapping.get(light, "Stand by")
