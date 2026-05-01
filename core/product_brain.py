from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

import yfinance as yf
import numpy as np

# ── Recommendations cache — prevent hammering yfinance ─────────────────────────
_RECS_CACHE: Dict[str, Any] = {}
_RECS_TTL = 180   # 3 minutes


class ProductBrain:
    def __init__(self) -> None:
        self.available = True
        self.last_symbols: List[str] = []
        self.last_intent: Optional[str] = None

        self.aliases = {
            "tesla": "TSLA",
            "tsla": "TSLA",
            "apple": "AAPL",
            "aapl": "AAPL",
            "nvidia": "NVDA",
            "nvda": "NVDA",
            "nvdia": "NVDA",
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
            "xlf": "XLF",
            "xlk": "XLK",
            "xlv": "XLV",
            "spy": "SPY",
            "qqq": "QQQ",
            "dia": "DIA",
            "iwm": "IWM",
            "tlt": "TLT",
            "gld": "GLD",
            "slv": "SLV",
            "ibit": "IBIT",
            "bito": "BITO",
            "etha": "ETHA",
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
            "bitcoin": "BTC",
            "btc": "BTC",
            "ethereum": "ETH",
            "eth": "ETH",
            "solana": "SOL",
            "sol": "SOL",
            "ripple": "XRP",
            "xrp": "XRP",
            "dogecoin": "DOGE",
            "doge": "DOGE",
            "cardano": "ADA",
            "ada": "ADA",
            # ampliaciÃ³n segura
            "tsm": "TSM",
            "shopify": "SHOP",
            "shop": "SHOP",
            "uber": "UBER",
            "rivian": "RIVN",
            "robinhood": "HOOD",
            "sofi": "SOFI",
            "super micro": "SMCI",
            "smci": "SMCI",
            "arkk": "ARKK",
            "smh": "SMH",
            "tan": "TAN",
            "bnb": "BNB",
            "avax": "AVAX",
        }

        self.direct_symbols = {
            "TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMZN", "NFLX",
            "COIN", "PLTR", "ARM", "MRVL", "OXY", "XOM", "CVX", "USO", "XLE",
            "XLF", "XLK", "XLV", "SPY", "QQQ", "DIA", "IWM", "TLT", "GLD", "SLV",
            "IBIT", "BITO", "ETHA", "AMD", "ORCL", "ADBE", "SNOW", "CRM", "ASML",
            "AVGO", "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA",
            "TSM", "SHOP", "UBER", "RIVN", "HOOD", "SOFI", "SMCI",
            "ARKK", "SMH", "TAN", "BNB", "AVAX",
        }

        self._ticker_stopwords = {
            "HOLA", "JARVIS", "HEY", "HI", "BUENAS", "BUENOS", "DIAS", "TARDES", "NOCHES",
            "ANALIZA", "ANALISIS", "ANÃLISIS", "NOTICIA", "NOTICIAS", "NEWS", "CATALIZADOR", "CATALIZADORES",
            "MEJOR", "TOP", "QUE", "QUÃ‰", "CUAL", "CUÃL", "ES", "SON", "DE", "DEL", "LA", "LAS", "EL", "LOS",
            "Y", "O", "UN", "UNA", "UNAS", "UNOS", "POR", "PARA", "CON", "SIN", "ESTA", "ESTE", "ESTAS", "ESTOS",
            "SEMANA", "HOY", "MANANA", "MAÃ‘ANA", "AYER", "DAME", "QUIERO", "PIDE", "PIDI", "PEDI", "PEDÃ",
            "ACCION", "ACCIONES", "STOCK", "STOCKS", "TICKER", "TICKERS", "SETUP", "TRADER", "COMPRA", "COMPRAR",
            "SELL", "VENDER", "VALE", "PENA", "NIVELES", "ENTRADA", "LASMISMAS", "ESAS", "MISMAS", "OPORTUNIDAD",
            "OPORTUNIDADES", "RECOMIEND", "COMPRAR", "VES", "DETALLE", "MAS", "MÃS", "DIO", "DI", "TE",
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
    def _remember_symbols(
    self,
    symbols: List[str],
     intent: Optional[str] = None) -> None:
        clean: List[str] = []
        for s in symbols:
            if s and s not in clean:
                clean.append(s)
        if clean:
            self.last_symbols = clean[:10]
        if intent:
            self.last_intent = intent

    def _context_symbols(self, text: str) -> List[str]:
        t = (text or "").lower()
        context_triggers = [
            "las que te pedi",
            "las que te pedÃ­",
            "las mismas",
            "esas",
            "esas acciones",
            "esas noticias",
            "de esas",
            "de las que te pedi",
            "de las que te pedÃ­",
            "de las acciones que te di",
            "de las acciones que te pedi",
            "de las acciones que te pedÃ­",
            "de los tickers que te di",
            "de los tickers que te pedi",
            "de los tickers que te pedÃ­",
        ]
        if any(trigger in t for trigger in context_triggers):
            return self.last_symbols[:]
        return []

    def _extract_symbols_from_text(self, text: str) -> List[str]:
        original = text or ""
        t = original.lower().strip()
        found: List[str] = []

        # 1) aliases
        for key, value in self.aliases.items():
            if re.search(rf"\b{re.escape(key)}\b", t):
                if value not in found:
                    found.append(value)

        tokens = re.findall(r"\b[A-Za-z]{1,10}\b", original)

        # 2) direct symbols
        for token in tokens:
            up = token.upper()
            if up in self.direct_symbols and up not in found:
                found.append(up)

        # 3) detecciÃ³n universal prudente
        market_cue = any(x in t for x in [
            "analiza", "analisis", "anÃ¡lisis", "noticia", "noticias", "news",
            "ticker", "tickers", "stock", "stocks", "accion", "acciÃ³n", "acciones",
            "trader", "setup", "compra", "comprar", "sell", "vender", "mejor",
            "top", "niveles", "entrada", "catalizador", "catalizadores"
        ])

        for token in tokens:
            up = token.upper()
            low = token.lower()

            if up in found:
                continue
            if len(up) > 5:
                continue
            if up in self._ticker_stopwords:
                continue

            # Caso 1: usuario escribiÃ³ ticker en mayÃºsculas
            if token.isupper():
                found.append(up)
                continue

            # Caso 2: estamos en contexto de mercado y no es una palabra
            # comÃºn/alias
            if market_cue and low not in self.aliases and up not in self._ticker_stopwords:
                found.append(up)

        return found

    def _resolve_symbol(self, text: str) -> Optional[str]:
        symbols = self._extract_symbols_from_text(text)
        if symbols:
            return symbols[0]
        return None

    def _normalize_market_symbol(self, symbol: str) -> str:
        crypto_map = {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "SOL": "SOL-USD",
            "XRP": "XRP-USD",
            "DOGE": "DOGE-USD",
            "ADA": "ADA-USD",
            "BNB": "BNB-USD",
            "AVAX": "AVAX-USD",
        }
        return crypto_map.get(symbol, symbol)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _safe_news(self, symbol: str) -> List[dict]:
        try:
            market_symbol = self._normalize_market_symbol(symbol)
            ticker = yf.Ticker(market_symbol)
            news = getattr(ticker, "news", None)
            if not news:
                return []

            items: List[dict] = []
            for item in news[:5]:
                title = item.get("title") or item.get(
                    "content", {}).get("title") or ""
                publisher = item.get("publisher") or item.get(
    "content", {}).get(
        "provider", {}).get("displayName") or ""
                link = item.get("link") or item.get(
    "content", {}).get(
        "canonicalUrl", {}).get("url") or ""
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

    def _format_multi_reply(self, items: List[Dict[str, Any]]) -> str:
        parts = []
        for item in items:
            parts.append(f"{item['symbol']} ({item['setup_score']})")
        return "Analisis rapido: " + ", ".join(parts)

    def _build_news_response(self, symbols: List[str]) -> dict:
        self._remember_symbols(symbols, intent="news")

        if len(symbols) == 1:
            symbol = symbols[0]
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

            bullets = "; ".join(
                [f"{n['publisher']}: {n['title']}" if n["publisher"] else n["title"] for n in news[:3]])
            return {
                "type": "chat",
                "reply": f"Noticias clave de {symbol}: {bullets}",
                "summary": f"Noticias de {symbol}",
                "details": {"symbol": symbol, "news": news},
                "action": "show_news",
                "confidence": 0.85,
                "source": "brain_news"
            }

        news_by_symbol: Dict[str, List[dict]] = {}
        summary_parts: List[str] = []

        for symbol in symbols:
            news = self._safe_news(symbol)
            news_by_symbol[symbol] = news
            if news:
                summary_parts.append(f"{symbol}: {news[0]['title']}")
            else:
                summary_parts.append(f"{symbol}: sin noticias claras")

        return {
            "type": "chat",
            "reply": " | ".join(summary_parts),
            "summary": "Multi noticias",
            "details": {"symbols": symbols, "news_by_symbol": news_by_symbol},
            "action": "show_news",
            "confidence": 0.85,
            "source": "brain_multi_news"
        }

    def _build_analysis_response(self, symbols: List[str]) -> dict:
        self._remember_symbols(symbols, intent="analysis")

        if len(symbols) == 1:
            symbol = symbols[0]
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

        items = [self.trader(symbol) for symbol in symbols]
        return {
            "type": "chat",
            "reply": self._format_multi_reply(items),
            "summary": "Multi analisis",
            "details": {"symbols": symbols, "items": items},
            "action": "show_multiple",
            "confidence": 0.9,
            "source": "brain_multi_trader"
        }

    def _build_best_response(self, symbols: List[str]) -> dict:
        items = [self.trader(symbol) for symbol in symbols]
        items = [item for item in items if item.get(
            "price") is not None or item.get("price_now") is not None]
        items = sorted(
    items, key=lambda x: x.get(
        "setup_score", 0), reverse=True)

        if not items:
            return {
                "type": "chat",
                "reply": "No veo suficiente informaciÃ³n para comparar esos activos ahora mismo.",
                "summary": "Sin comparaciÃ³n",
                "details": {"items": []},
                "action": "",
                "confidence": 0.5,
                "source": "brain_followup"
            }

        best = items[0]
        self._remember_symbols(symbols, intent="best")

        return {
            "type": "chat",
            "reply": f"La mejor ahora mismo es {best['symbol']} con score {best['setup_score']}.",
            "summary": "Best asset",
            "details": {"items": items},
            "action": "show_multiple",
            "confidence": 0.9,
            "source": "brain_followup"
        }

    # =========================
    # CHAT
    # =========================
    def chat(self, message: str) -> dict:
        text = (message or "").strip()
        lower = text.lower()

        if lower in [
    "hola",
    "hola jarvis",
    "hey",
    "hi",
    "buenas",
    "buenos dias",
    "buenas tardes",
     "buenas noches"]:
            return {
                "type": "chat",
                "reply": "Hola Juan. Que necesitas hoy?",
                "summary": "Saludo inicial",
                "details": {},
                "action": "",
                "confidence": 1.0,
                "source": "brain_simple"
            }

        explicit_symbols = self._extract_symbols_from_text(text)
        symbols = explicit_symbols[:]

        if not symbols:
            symbols = self._context_symbols(text)

        if explicit_symbols:
            self._remember_symbols(explicit_symbols)

        if any(x in lower for x in [
            "oportunidad", "oportunidades", "recomiend", "mejor accion", "acciones para",
            "que comprar", "quÃ© comprar", "que ves esta semana", "oportunidades para esta semana"
        ]):
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

                self._remember_symbols([x["symbol"]
                                       for x in items], intent="recommendations")

                top = ", ".join(
                    [f"{x['symbol']} ({x['setup_score']})" for x in items[:3]])
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

        wants_news = any(
    x in lower for x in [
        "noticia",
        "noticias",
        "news",
        "catalizador",
         "catalizadores"])
        wants_analysis = any(x in lower for x in [
            "analiza", "analisis", "anÃ¡lisis", "vale la pena", "comprar", "compra", "buy",
            "sell", "vender", "trader", "setup", "ticker", "accion", "acciÃ³n", "stock", "niveles", "entrada"
        ])
        wants_best = any(x in lower for x in [
            "cual es mejor", "cuÃ¡l es mejor", "mejor", "top", "best"
        ])

        # Follow-up real sin romper nada
        if wants_news and not symbols and self.last_symbols:
            return self._build_news_response(self.last_symbols)

        if wants_analysis and not symbols and self.last_symbols:
            return self._build_analysis_response(self.last_symbols)

        if wants_best and self.last_symbols:
            target_symbols = symbols if symbols else self.last_symbols
            return self._build_best_response(target_symbols)

        if symbols and wants_news:
            return self._build_news_response(symbols)

        if symbols and wants_analysis:
            return self._build_analysis_response(symbols)

        if len(symbols) == 1:
            symbol = symbols[0]
            return {
                "type": "chat",
                "reply": f"Detecte {symbol}. Si quieres te doy analisis, noticias o niveles de entrada.",
                "summary": f"Ticker detectado: {symbol}",
                "details": {"symbol": symbol},
                "action": "ask_followup",
                "confidence": 0.8,
                "source": "brain_symbol_detect"
            }

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

    def _enrich_asset_metadata(self, symbol: str) -> dict:
        symbol = (symbol or "").upper()

        crypto = ["BTC", "ETH", "SOL", "XRP", "BTC-USD", "ETH-USD", "SOL-USD"]
        etf = ["SPY", "QQQ", "XLE", "GLD", "SHY", "USO", "BITO", "IBIT"]

        if symbol in crypto or symbol.endswith("-USD"):
            return {"asset_type": "crypto", "region": "global", "sector": "crypto"}

        if symbol in etf:
            return {"asset_type": "etf", "region": "usa", "sector": "macro"}

        if ".NS" in symbol:
            return {"asset_type": "stock", "region": "india", "sector": "nse"}

        tech = ["NVDA", "AAPL", "MSFT", "GOOGL", "META"]
        energy = ["XOM", "CVX", "OXY"]

        if symbol in tech:
            return {"asset_type": "stock", "region": "usa", "sector": "tech"}

        if symbol in energy:
            return {"asset_type": "stock", "region": "usa", "sector": "energy"}

        return {"asset_type": "stock", "region": "usa", "sector": "general"}

    def trader(self, symbol: str) -> Dict[str, Any]:
        symbol = (symbol or "").upper().strip()
        market_symbol = self._normalize_market_symbol(symbol)

        try:
            data = yf.Ticker(market_symbol).history(
    period="3mo", interval="1d", auto_adjust=False)

            if data is None or data.empty:
                raise ValueError("No data")

            close = data["Close"].dropna()
            if len(close) < 20:
                raise ValueError("Not enough data")

            price = float(close.iloc[-1])
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(min(50, len(close))).mean().iloc[-1])

            momentum_5 = (close.iloc[-1] - close.iloc[-5]) / \
                          close.iloc[-5] * 100 if len(close) >= 5 else 0.0
            momentum_20 = (close.iloc[-1] - close.iloc[-20]) / \
                           close.iloc[-20] * 100 if len(close) >= 20 else 0.0
            vol = float(np.std(close.tail(min(10, len(close)))))

            # Convert vol to percentage so high-priced symbols (NVDA $900+, BTC $60k+)
            # aren't unfairly penalised by dollar-denominated std deviation
            vol_pct = round(vol / max(price, 1.0) * 100, 2)

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

            # Wide neutral band (1.2–5%) avoids inflating scores for all normal-vol stocks
            if vol_pct < 1.2:
                score += 4
            elif vol_pct > 10.0:
                score -= 8
            elif vol_pct > 5.0:
                score -= 4

            score = max(0, min(100, int(score)))

            # Buy: score >= 90 AND positive 20d momentum (declining stocks never Buy)
            # Watch: score >= 60 (setup exists but not confirmed)
            # Avoid: score < 60
            # Calibrated for ~33% Buy / ~42% Watch / ~25% Avoid in neutral-to-bull markets
            if score >= 90 and momentum_20 >= 0:
                signal = "Buy"
                action = "BUY"
                light  = "green"
            elif score >= 60:
                signal = "Watch"
                action = "WATCH"
                light  = "yellow"
            else:
                signal = "Avoid"
                action = "AVOID"
                light  = "red"

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

            # Sector context reuses metadata already computed above
            _sector_meta = self._enrich_asset_metadata(symbol)
            _sector = _sector_meta.get("sector", "general")
            _sector_context = {
                "tech":    "Sector tech impulsado por IA y resultados de mega-cap.",
                "energy":  "Sector energia afectado por dinamica petroleo y geopolitica.",
                "crypto":  "Cripto con volatilidad estructural alta por liquidez macro.",
                "macro":   "ETF de referencia con correlacion al regimen macro.",
                "general": "Catalizadores mixtos segun condiciones generales del mercado.",
            }.get(_sector, "Condiciones de mercado estandar.")

            m20_str = f"{round(momentum_20, 1)}%"
            sma20_str = str(round(sma20, 2))
            sma50_str = str(round(sma50, 2))
            vol_str = f"{vol_pct}%"

            if signal == "Buy":
                friendly = (
                    f"Setup solido - score {score}/100. "
                    f"Momentum {m20_str} en 20d. Precio sobre SMA20 y SMA50. "
                    "Entrada con riesgo controlado."
                )
                thesis_short = (
                    f"{symbol} sobre SMA20 ({sma20_str}) y SMA50 ({sma50_str}) "
                    f"con momentum positivo ({m20_str} en 20d). Fortaleza relativa confirmada."
                )
                catalyst = (
                    "Momentum tecnico confirmado. "
                    "Verificar earnings proximos o catalizadores de sector antes de entrar."
                )
                analysis = (
                    f"{symbol} muestra momentum fuerte ({m20_str} en 20d) "
                    f"con precio sobre SMA20 ({sma20_str}) y SMA50 ({sma50_str}). "
                    f"Volatilidad {vol_str}/dia - controlada. "
                    f"{_sector_context}"
                )
                risk = (
                    f"Riesgo moderado. Volatilidad {vol_str}. "
                    f"Stop sugerido: {round(stop_pct * 100, 1)}% bajo entrada. "
                    "Exposicion max: 1-2% del portafolio."
                )
            elif signal == "Watch":
                friendly = (
                    f"Setup aceptable - score {score}/100. "
                    "Senales mixtas - esperar confirmacion antes de entrar."
                )
                thesis_short = (
                    f"{symbol} con senales mixtas. Momentum {m20_str} en 20d. "
                    f"Precio cerca de SMA20 ({sma20_str}) - esperar ruptura confirmada."
                )
                catalyst = "Sin catalizador tecnico decisivo. Posicion de espera recomendada."
                analysis = (
                    f"{symbol} con momentum {m20_str} en 20d. "
                    f"Senales mixtas - precio cerca de SMA20 ({sma20_str}). "
                    f"Volatilidad {vol_str}/dia. "
                    f"{_sector_context}"
                )
                risk = (
                    f"Riesgo medio-alto. Volatilidad {vol_str}. "
                    "Confirmar tendencia antes de entrar. "
                    "No arriesgar mas del 1% del portafolio."
                )
            else:
                friendly = (
                    f"Setup debil - score {score}/100. "
                    "Riesgo elevado frente al beneficio esperado. No operar ahora."
                )
                thesis_short = (
                    f"{symbol} bajo medias clave. Momentum debil ({m20_str} en 20d). "
                    "Evitar nueva posicion."
                )
                catalyst = "Sin catalizador tecnico verificado. Evitar entrada."
                analysis = (
                    f"{symbol} muestra momentum debil ({m20_str} en 20d) "
                    f"con precio bajo medias clave (SMA20: {sma20_str}). "
                    f"Volatilidad {vol_str}/dia - riesgo elevado. "
                    f"{_sector_context}"
                )
                risk = (
                    f"Riesgo elevado. Volatilidad {vol_str}. "
                    f"Stop: no aplicable - evitar posicion nueva. "
                    "Reducir exposicion existente si la hay."
                )

            return {
                "symbol":               symbol,
                "price":                round(price, 2),
                "price_now":            round(price, 2),
                "setup_score":          score,
                "signal":               signal,
                "traffic_light":        light,
                "thesis_short":         thesis_short,
                "catalyst":             catalyst,
                "risk":                 risk,
                "analysis":             analysis,
                "last_updated":         datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "trade_plan": {
                    "action":               action,
                    "entry_zone":           [entry_low, entry_high],
                    "stop_loss":            stop_loss,
                    "target_1":             target_1,
                    "target_2":             target_2,
                    "risk_reward_estimate": 1.2,
                },
                "insight_lines":        insight_lines,
                "summary":              f"{symbol} | precio {round(price, 2)} | score {score} | {signal}",
                "friendly_recommendation": friendly,
                **_sector_meta,
                "source": "product_brain"
            }

        except Exception:
            return {
                "symbol":                  symbol,
                "price":                   None,
                "price_now":               None,
                "setup_score":             0,
                "signal":                  "Avoid",
                "traffic_light":           "red",
                "thesis_short":            "Sin datos disponibles para análisis.",
                "catalyst":                "No hay catalizador verificado. Sin datos de noticias recientes disponibles.",
                "risk":                    "No se puede calcular riesgo — datos insuficientes.",
                "analysis":                "Datos insuficientes para análisis. Intentar con otro símbolo o verificar conectividad.",
                "last_updated":            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "trade_plan": {
                    "action":               "AVOID",
                    "entry_zone":           [],
                    "stop_loss":            "-",
                    "target_1":             "-",
                    "target_2":             "-",
                    "risk_reward_estimate": "-"
                },
                "insight_lines":           ["No hay datos suficientes."],
                "summary":                 f"{symbol} sin datos",
                "friendly_recommendation": "No operar.",
                **self._enrich_asset_metadata(symbol),
                "source": "product_brain"
            }

    # =========================
    # RECOMMENDATIONS
    # =========================
    def recommendations(self) -> Dict[str, Any]:
        now = time.time()
        cached = _RECS_CACHE.get("recs")
        if cached and now - cached.get("_ts", 0) < _RECS_TTL:
            return {k: v for k, v in cached.items() if k != "_ts"}

        symbols = [
            # USA MEGA-CAP
            "AAPL", "MSFT", "GOOGL", "AMZN", "META",
            # USA TECH / GROWTH
            "NVDA", "AMD", "TSLA", "PLTR", "SMCI",
            # FINANCE / MACRO ETFs
            "XOM", "CVX", "XLE",
            # CRYPTO (yfinance format)
            "BTC-USD", "ETH-USD",
            # HIGH-BETA
            "COIN", "HOOD",
        ]

        results: List[Dict[str, Any]] = []

        def _fetch(sym: str):
            try:
                r = self.trader(sym)
                if r.get("price") is not None:
                    return r
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_fetch, s): s for s in symbols}
            for fut in as_completed(futures, timeout=20):
                r = fut.result()
                if r:
                    results.append(r)

        results = sorted(results, key=lambda x: x.get("setup_score", 0), reverse=True)
        output = {"items": results[:12]}
        _RECS_CACHE["recs"] = {**output, "_ts": now}
        return output
