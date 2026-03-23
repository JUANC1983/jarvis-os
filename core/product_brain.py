from __future__ import annotations

from typing import Dict, Any, List, Optional
import re

import yfinance as yf
import numpy as np


class ProductBrain:
    def __init__(self) -> None:
        self.available = True

        self.aliases = {
            "tesla": "TSLA",
            "tsla": "TSLA",
            "apple": "AAPL",
            "aapl": "AAPL",
            "nvidia": "NVDA",
            "nvda": "NVDA",
            "microsoft": "MSFT",
            "msft": "MSFT",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "googl": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "amazon": "AMZN",
            "amzn": "AMZN",
            "netflix": "NFLX",
            "nflx": "NFLX",
            "coinbase": "COIN",
            "coin": "COIN",
            "palantir": "PLTR",
            "pltr": "PLTR",
            "arm": "ARM",
            "marvell": "MRVL",
            "mrvl": "MRVL",
            "oxy": "OXY",
            "occidental": "OXY",
            "exxon": "XOM",
            "xom": "XOM",
            "chevron": "CVX",
            "cvx": "CVX",
            "uso": "USO",
            "xle": "XLE",
            "amd": "AMD",
            "oracle": "ORCL",
            "orcl": "ORCL",
            "adobe": "ADBE",
            "adbe": "ADBE",
            "snowflake": "SNOW",
            "snow": "SNOW",
            "crm": "CRM",
            "salesforce": "CRM",
            "asml": "ASML",
            "avgo": "AVGO",
            "broadcom": "AVGO",
        }

    # =========================
    # HEALTH
    # =========================
    def health(self) -> dict:
        return {
            "available": True,
            "boot_errors": [],
            "orchestrator_available": True,
        }

    # =========================
    # HELPERS
    # =========================
    def _extract_symbol_from_text(self, text: str) -> Optional[str]:
        t = (text or "").lower().strip()

        # exact aliases first
        for key, value in self.aliases.items():
            if re.search(rf"\b{re.escape(key)}\b", t):
                return value

        # uppercase ticker-like token
        tokens = re.findall(r"\b[A-Za-z]{1,5}\b", text or "")
        for token in tokens:
            up = token.upper()
            if up in set(self.aliases.values()):
                return up

        return None

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _safe_news(self, symbol: str) -> List[dict]:
        try:
            ticker = yf.Ticker(symbol)
            news = getattr(ticker, "news", None)
            if not news:
                return []

            items: List[dict] = []
            for item in news[:5]:
                title = item.get("title") or item.get("content", {}).get("title") or ""
                publisher = item.get("publisher") or item.get("content", {}).get("provider", {}).get("displayName") or ""
                link = item.get("link") or item.get("content", {}).get("canonicalUrl", {}).get("url") or ""
                if title:
                    items.append({
                        "title": str(title),
                        "publisher": str(publisher),
                        "link": str(link),
                    })
            return items
        except Exception:
            return []

    def _format_trade_reply(self, result: Dict[str, Any]) -> str:
        symbol = result.get("symbol", "-")
        price = result.get("price_now", result.get("price"))
        score = result.get("setup_score", "-")
        action = ((result.get("trade_plan") or {}).get("action")) or "-"
        insight_lines = result.get("insight_lines") or []

        line1 = f"{symbol}: precio {price} | score {score} | accion {action}"
        if insight_lines:
            line2 = insight_lines[0]
            return f"{line1}. {line2}"
        return line1

    # =========================
    # CHAT
    # =========================
    def chat(self, message: str) -> dict:
        text = (message or "").strip()
        lower = text.lower()

        # saludo simple
        if lower in ["hola", "hola jarvis", "hey", "hi", "buenas", "buenos dias", "buenas tardes", "buenas noches"]:
            return {
                "type": "chat",
                "reply": "Hola Juan. Que necesitas hoy?",
                "summary": "Saludo inicial",
                "details": {},
                "action": "",
                "confidence": 1.0,
                "source": "brain_simple"
            }

        # recomendaciones / oportunidades
        if any(x in lower for x in ["oportunidad", "oportunidades", "recomiend", "mejor accion", "acciones para", "que comprar", "que ves esta semana"]):
            try:
                recs = self.recommendations()
                items = recs.get("items", [])[:5]

                if not items:
                    return {
                        "type": "chat",
                        "reply": "Ahora mismo no veo setups claros.",
                        "summary": "Sin oportunidades",
                        "details": {"items": []},
                        "action": "",
                        "confidence": 0.7,
                        "source": "brain_simple"
                    }

                top = ", ".join([f"{x['symbol']} ({x['setup_score']})" for x in items[:3]])
                return {
                    "type": "chat",
                    "reply": f"Las mejores oportunidades ahora son: {top}. Si quieres, te analizo una en detalle.",
                    "summary": "Top oportunidades",
                    "details": {"items": items},
                    "action": "show_recommendations",
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

        # detectar ticker automatico para analisis
        symbol = self._extract_symbol_from_text(text)
        wants_analysis = any(x in lower for x in [
            "analiza", "analisis", "vale la pena", "comprar", "compra", "buy",
            "sell", "vender", "trader", "setup", "ticker", "accion", "stock"
        ])

        if symbol and wants_analysis:
            result = self.trader(symbol)
            return {
                "type": "chat",
                "reply": self._format_trade_reply(result),
                "summary": result.get("summary", f"{symbol} analizado"),
                "details": result,
                "action": "show_trader",
                "confidence": 0.92,
                "source": "brain_trader_router"
            }

        # noticias automaticas por simbolo
        if symbol and any(x in lower for x in ["noticia", "noticias", "news", "catalizador", "catalizadores"]):
            news = self._safe_news(symbol)
            if not news:
                return {
                    "type": "chat",
                    "reply": f"No encontre noticias recientes claras para {symbol}.",
                    "summary": f"Sin noticias para {symbol}",
                    "details": {"symbol": symbol, "news": []},
                    "action": "",
                    "confidence": 0.6,
                    "source": "brain_news"
                }

            bullets = "; ".join([f"{n['publisher']}: {n['title']}" if n["publisher"] else n["title"] for n in news[:3]])
            return {
                "type": "chat",
                "reply": f"Noticias clave de {symbol}: {bullets}",
                "summary": f"Noticias de {symbol}",
                "details": {"symbol": symbol, "news": news},
                "action": "show_news",
                "confidence": 0.85,
                "source": "brain_news"
            }

        # si detecta simbolo pero no intencion exacta, guiar
        if symbol:
            return {
                "type": "chat",
                "reply": f"Detecte {symbol}. Si quieres te doy analisis, noticias o niveles de entrada.",
                "summary": f"Ticker detectado: {symbol}",
                "details": {"symbol": symbol},
                "action": "ask_followup",
                "confidence": 0.8,
                "source": "brain_symbol_detect"
            }

        # fallback
        return {
            "type": "chat",
            "reply": "Dime que necesitas: analisis de una accion, oportunidades de la semana, noticias o tareas.",
            "summary": "Fallback",
            "details": {},
            "action": "",
            "confidence": 0.6,
            "source": "brain_simple"
        }

    # =========================
    # TRADER
    # =========================
    def trader(self, symbol: str) -> Dict[str, Any]:
        symbol = (symbol or "").upper().strip()

        try:
            data = yf.Ticker(symbol).history(period="3mo", interval="1d", auto_adjust=False)

            if data is None or data.empty:
                raise ValueError("No data")

            close = data["Close"].dropna()
            if len(close) < 20:
                raise ValueError("Not enough data")

            price = float(close.iloc[-1])
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(min(50, len(close))).mean().iloc[-1])

            momentum_5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0.0
            momentum_20 = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100 if len(close) >= 20 else 0.0
            vol = float(np.std(close.tail(min(10, len(close)))))

            score = 50

            if price > sma20:
                score += 12
            else:
                score -= 10

            if price > sma50:
                score += 12
            else:
                score -= 10

            if momentum_20 > 10:
                score += 18
            elif momentum_20 > 3:
                score += 10
            elif momentum_20 < -10:
                score -= 18
            elif momentum_20 < 0:
                score -= 8

            if momentum_5 > 3:
                score += 8
            elif momentum_5 > 0:
                score += 4
            elif momentum_5 < -3:
                score -= 8
            elif momentum_5 < 0:
                score -= 4

            if vol < 5:
                score += 4
            elif vol > 15:
                score -= 6

            score = max(0, min(100, int(score)))

            if score >= 80:
                action = "GO"
                light = "green"
            elif score >= 60:
                action = "WAIT"
                light = "yellow"
            else:
                action = "AVOID"
                light = "red"

            band = max(0.015, min(0.08, vol / max(price, 1.0)))
            stop_pct = max(0.025, min(0.10, band * 1.8))
            target1_pct = max(0.03, min(0.12, stop_pct * 1.2))
            target2_pct = max(0.05, min(0.20, stop_pct * 2.0))

            entry_low = round(price * (1 - band * 0.6), 2)
            entry_high = round(price * (1 + band * 0.4), 2)
            stop_loss = round(price * (1 - stop_pct), 2)
            target_1 = round(price * (1 + target1_pct), 2)
            target_2 = round(price * (1 + target2_pct), 2)

            insight_lines = [
                "Tendencia de corto plazo favorable." if price > sma20 else "Debilidad de corto plazo.",
                "Precio sobre media intermedia." if price > sma50 else "Precio por debajo de media intermedia.",
                f"Momentum 5d: {round(momentum_5, 2)}%",
                f"Momentum 20d: {round(momentum_20, 2)}%",
            ]

            if score >= 80:
                friendly = "Setup fuerte. Solo entrar si confirma y con riesgo controlado."
            elif score >= 60:
                friendly = "Setup aceptable. Mejor esperar una entrada mas limpia."
            else:
                friendly = "Ahora no es una entrada limpia. Riesgo alto frente al beneficio esperado."

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "price_now": round(price, 2),
                "setup_score": score,
                "traffic_light": light,
                "trade_plan": {
                    "action": action,
                    "entry_zone": [entry_low, entry_high],
                    "stop_loss": stop_loss,
                    "target_1": target_1,
                    "target_2": target_2,
                    "risk_reward_estimate": 1.2,
                },
                "insight_lines": insight_lines,
                "summary": f"{symbol} | precio {round(price, 2)} | score {score} | accion {action}",
                "friendly_recommendation": friendly,
                "source": "product_brain"
            }

        except Exception:
            return {
                "symbol": symbol,
                "price": None,
                "price_now": None,
                "setup_score": 0,
                "traffic_light": "red",
                "trade_plan": {
                    "action": "AVOID",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-"
                },
                "insight_lines": ["No hay datos suficientes."],
                "summary": f"{symbol} sin datos",
                "friendly_recommendation": "No operar.",
                "source": "product_brain"
            }

    # =========================
    # RECOMMENDATIONS
    # =========================
    def recommendations(self) -> Dict[str, Any]:
        symbols = [
            "NVDA", "AMD", "META", "MSFT", "GOOGL",
            "PLTR", "COIN", "ARM", "MRVL",
            "XOM", "CVX", "OXY", "XLE", "USO"
        ]

        results = []
        for s in symbols:
            r = self.trader(s)
            if r["price"] is not None:
                results.append(r)

        results = sorted(results, key=lambda x: x["setup_score"], reverse=True)
        return {"items": results[:8]}
