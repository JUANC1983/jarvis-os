import time
from typing import Any, Dict, List

import yfinance as yf
import pandas as pd

from core.exceptions import ExternalServiceError

_QUOTE_CACHE: Dict[str, Dict] = {}
_QUOTE_TTL   = 120   # seconds


def _cached_quote(symbol: str) -> Dict[str, Any]:
    """Return cached quote if fresh, else fetch and cache."""
    now = time.time()
    entry = _QUOTE_CACHE.get(symbol)
    if entry and now - entry["_ts"] < _QUOTE_TTL:
        return entry
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info
        price          = info.get("lastPrice")
        previous_close = info.get("previousClose")
        currency       = info.get("currency")
        change = (price - previous_close) if (price and previous_close) else None
        change_pct = (change / previous_close * 100) if (change and previous_close) else None
        result = {
            "symbol": symbol, "price": price, "previous_close": previous_close,
            "change": change, "change_pct": change_pct, "currency": currency, "_ts": now,
        }
    except Exception as exc:
        result = {
            "symbol": symbol, "price": None, "previous_close": None,
            "change": None, "change_pct": None, "currency": None, "_ts": now,
            "error": str(exc),
        }
    _QUOTE_CACHE[symbol] = result
    return result


class MarketDataEngine:
    def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for raw_symbol in symbols:
            symbol = raw_symbol.upper().strip()
            # Normalise crypto symbols for yfinance
            if symbol in ("BTC", "ETH", "SOL", "XRP", "DOGE"):
                symbol = symbol + "-USD"
            entry = _cached_quote(symbol)
            results.append({k: v for k, v in entry.items() if k != "_ts"})
        return results

    def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> Dict[str, Any]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            rows: List[Dict[str, Any]] = []
            if not hist.empty:
                hist = hist.reset_index()
                for _, row in hist.iterrows():
                    rows.append(
                        {
                            "datetime": str(row.iloc[0]),
                            "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
                            "high": float(row["High"]) if pd.notna(row["High"]) else None,
                            "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
                            "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
                            "volume": float(row["Volume"]) if pd.notna(row["Volume"]) else None,
                        }
                    )

            return {
                "symbol": symbol.upper(),
                "period": period,
                "interval": interval,
                "rows": rows,
            }
        except Exception as exc:
            raise ExternalServiceError(f"Market history failed for {symbol}: {exc}") from exc
