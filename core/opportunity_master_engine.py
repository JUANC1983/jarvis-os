from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List, Optional

import yfinance as yf

from core.market_universe_engine import MarketUniverseEngine
from core.news_catalyst_engine import NewsCatalystEngine


class OpportunityMasterEngine:
    def __init__(self) -> None:
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.cache_path = os.path.join(self.base_dir, "memory", "opportunity_cache.json")
        self.universe_engine = MarketUniverseEngine()
        self.news_engine = NewsCatalystEngine()

        self.alias_map = {
            "TESLA": "TSLA",
            "GOOGLE": "GOOGL",
            "ALPHABET": "GOOGL",
            "FACEBOOK": "META",
            "META": "META",
            "APPLE": "AAPL",
            "MICROSOFT": "MSFT",
            "NVIDIA": "NVDA",
            "AMAZON": "AMZN",
            "BERKSHIRE": "BRK-B",
            "NETFLIX": "NFLX",
            "PALANTIR": "PLTR",
            "COINBASE": "COIN",
            "ORO": "GLD",
            "GOLD": "GLD",
            "PLATA": "SLV",
            "SILVER": "SLV",
            "PETROLEO": "USO",
            "OIL": "USO",
            "GAS": "UNG",
        }

    def resolve_symbol(self, raw: str) -> str:
        value = str(raw).strip().upper().replace(".", "-")
        return self.alias_map.get(value, value)

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            if math.isnan(float(value)):
                return default
            return float(value)
        except Exception:
            return default

    def _traffic(self, score: int) -> str:
        if score >= 80:
            return "green"
        if score >= 60:
            return "yellow"
        return "red"

    def _action(self, score: int) -> str:
        if score >= 80:
            return "GO"
        if score >= 60:
            return "WAIT"
        return "AVOID"

    def _friendly_text(self, score: int) -> str:
        if score >= 80:
            return "Setup fuerte. Solo entrar si el precio confirma y el riesgo está controlado."
        if score >= 60:
            return "Setup aceptable. Mejor esperar una entrada más limpia."
        return "Ahora no es una entrada limpia. Riesgo alto frente al beneficio esperado."

    def _load_cache(self) -> Optional[Dict]:
        if not os.path.exists(self.cache_path):
            return None

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, payload: Dict) -> None:
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _extract_symbol_frame(self, downloaded, symbol: str):
        try:
            if downloaded is None or downloaded.empty:
                return None

            if hasattr(downloaded.columns, "nlevels") and downloaded.columns.nlevels > 1:
                if symbol not in downloaded.columns.get_level_values(0):
                    return None
                frame = downloaded[symbol].copy()
            else:
                frame = downloaded.copy()

            if frame is None or frame.empty:
                return None

            needed = ["Open", "High", "Low", "Close", "Volume"]
            for col in needed:
                if col not in frame.columns:
                    return None

            return frame.dropna()
        except Exception:
            return None

    def _build_trade_plan(self, price: float, score: int, atr_pct: float) -> Dict:
        band = max(0.012, atr_pct * 1.2)
        risk = max(0.025, atr_pct * 1.5)

        if score >= 80:
            entry_low = price * (1 - band * 0.6)
            entry_high = price * (1 + band * 0.5)
            stop = price * (1 - risk)
            target_1 = price * (1 + risk * 1.2)
            target_2 = price * (1 + risk * 2.0)
        elif score >= 60:
            entry_low = price * (1 - band)
            entry_high = price * (1 - band * 0.15)
            stop = price * (1 - risk * 1.1)
            target_1 = price * (1 + risk * 0.9)
            target_2 = price * (1 + risk * 1.5)
        else:
            entry_low = price * (1 - band * 1.5)
            entry_high = price * (1 - band * 0.8)
            stop = price * (1 - risk * 1.25)
            target_1 = price * (1 + risk * 0.5)
            target_2 = price * (1 + risk)

        rr = 0.0
        risk_amount = max(price - stop, 0.01)
        reward_amount = max(target_1 - price, 0.01)
        rr = round(reward_amount / risk_amount, 2)

        return {
            "action": self._action(score),
            "entry_zone": [round(entry_low, 2), round(entry_high, 2)],
            "stop_loss": round(stop, 2),
            "target_1": round(target_1, 2),
            "target_2": round(target_2, 2),
            "risk_reward_estimate": rr,
        }

    def _analyze_frame(self, symbol: str, frame) -> Optional[Dict]:
        try:
            if frame is None or frame.empty or len(frame) < 70:
                return None

            close = frame["Close"]
            high = frame["High"]
            low = frame["Low"]
            volume = frame["Volume"]

            price = self._safe_float(close.iloc[-1])
            sma20 = self._safe_float(close.tail(20).mean())
            sma50 = self._safe_float(close.tail(50).mean())
            sma200 = self._safe_float(close.tail(min(200, len(close))).mean())
            momentum_5 = ((price / self._safe_float(close.iloc[-6], price)) - 1) * 100 if len(close) >= 6 else 0.0
            momentum_20 = ((price / self._safe_float(close.iloc[-21], price)) - 1) * 100 if len(close) >= 21 else 0.0
            rel_vol = self._safe_float(volume.iloc[-1]) / max(self._safe_float(volume.tail(20).mean()), 1.0)
            high_20 = self._safe_float(high.tail(20).max())
            low_20 = self._safe_float(low.tail(20).min())
            range_pct = (high_20 - low_20) / max(price, 1.0)
            atr_pct = max(range_pct / 4.0, 0.015)

            score = 50

            if price > sma20:
                score += 8
            else:
                score -= 8

            if price > sma50:
                score += 10
            else:
                score -= 10

            if price > sma200:
                score += 8
            else:
                score -= 8

            if sma20 > sma50:
                score += 10
            else:
                score -= 10

            if momentum_20 > 12:
                score += 18
            elif momentum_20 > 5:
                score += 12
            elif momentum_20 > 0:
                score += 6
            elif momentum_20 < -8:
                score -= 14
            elif momentum_20 < 0:
                score -= 6

            if momentum_5 > 4:
                score += 8
            elif momentum_5 > 0:
                score += 4
            elif momentum_5 < -4:
                score -= 8
            elif momentum_5 < 0:
                score -= 4

            if rel_vol > 1.8:
                score += 12
            elif rel_vol > 1.25:
                score += 8
            elif rel_vol > 1.0:
                score += 4
            elif rel_vol < 0.7:
                score -= 4

            breakout_distance = (high_20 - price) / max(price, 1.0)
            if breakout_distance <= 0.015 and price >= sma20 and price >= sma50:
                score += 10

            if price > low_20 * 1.12 and price < high_20 * 0.98 and price > sma50:
                score += 6

            news = self.news_engine.analyze(symbol)
            score += int(news.get("catalyst_score", 0))

            score = max(0, min(100, int(score)))
            traffic = self._traffic(score)
            trade_plan = self._build_trade_plan(price, score, atr_pct)

            insight_lines: List[str] = []

            if price > sma20 and price > sma50:
                insight_lines.append("Tendencia de corto y medio plazo favorable.")
            elif price > sma20:
                insight_lines.append("Mejora táctica de corto plazo.")
            else:
                insight_lines.append("Debilidad de corto plazo.")

            if rel_vol > 1.25:
                insight_lines.append("Volumen por encima de lo normal, señal útil para seguimiento.")
            elif rel_vol < 0.8:
                insight_lines.append("Volumen flojo; falta convicción.")
            else:
                insight_lines.append("Volumen neutral.")

            insight_lines.append(f"Momentum 5d: {momentum_5:.2f}% | Momentum 20d: {momentum_20:.2f}%")
            insight_lines.append(news.get("catalyst_summary", "Sin catalizador fuerte detectado en noticias recientes."))

            friendly = self._friendly_text(score)

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "price_now": round(price, 2),
                "setup_score": score,
                "traffic_light": traffic,
                "trade_plan": trade_plan,
                "insight_lines": insight_lines[:4],
                "summary": f"{symbol} | precio {round(price, 2)} | score {score} | acción {trade_plan['action']}",
                "friendly_recommendation": friendly,
                "source": "opportunity_master",
            }

        except Exception:
            return None

    def analyze_symbol(self, raw_symbol: str) -> Dict:
        symbol = self.resolve_symbol(raw_symbol)

        try:
            frame = yf.download(
                tickers=symbol,
                period="9mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
        except Exception:
            frame = None

        parsed = self._extract_symbol_frame(frame, symbol)
        result = self._analyze_frame(symbol, parsed)

        if result:
            return result

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
                "risk_reward_estimate": "-",
            },
            "insight_lines": [f"No se pudo obtener información suficiente para {symbol}."],
            "summary": f"{symbol} sin suficiente contexto todavía.",
            "friendly_recommendation": "No hay datos suficientes para una decisión seria.",
            "source": "opportunity_master",
        }

    def get_top_opportunities(self, limit: int = 8, force_refresh: bool = False) -> List[Dict]:
        ttl_seconds = int(os.getenv("OPPORTUNITY_CACHE_TTL_SECONDS", "900"))
        cached = self._load_cache()

        if (
            not force_refresh
            and cached
            and isinstance(cached, dict)
            and (time.time() - float(cached.get("generated_at", 0))) < ttl_seconds
            and isinstance(cached.get("items"), list)
            and cached.get("items")
        ):
            return cached["items"][:limit]

        universe = self.universe_engine.get_universe()
        if not universe:
            return []

        batch_size = int(os.getenv("MARKET_SCAN_BATCH_SIZE", "80"))
        raw_results: List[Dict] = []

        for i in range(0, len(universe), batch_size):
            batch = universe[i:i + batch_size]
            tickers = " ".join(batch)

            try:
                downloaded = yf.download(
                    tickers=tickers,
                    period="9mo",
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    threads=True,
                    group_by="ticker",
                )
            except Exception:
                downloaded = None

            for symbol in batch:
                frame = self._extract_symbol_frame(downloaded, symbol)
                result = self._analyze_frame(symbol, frame)
                if result:
                    raw_results.append(result)

        raw_results.sort(key=lambda x: (x.get("setup_score", 0), x.get("price_now") is not None), reverse=True)

        green = [x for x in raw_results if x.get("traffic_light") == "green"]
        yellow = [x for x in raw_results if x.get("traffic_light") == "yellow"]

        final_items: List[Dict] = []
        final_items.extend(green[: max(3, min(limit, len(green)))])
        final_items.extend([x for x in yellow if x["symbol"] not in {y["symbol"] for y in final_items}])

        if len(final_items) < limit:
            used = {x["symbol"] for x in final_items}
            for item in raw_results:
                if item["symbol"] in used:
                    continue
                final_items.append(item)
                if len(final_items) >= limit:
                    break

        final_items = final_items[:limit]

        self._save_cache({
            "generated_at": time.time(),
            "universe_size": len(universe),
            "items": final_items,
        })

        return final_items
