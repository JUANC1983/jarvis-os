from typing import Any, Dict, List

import yfinance as yf
import pandas as pd

from core.exceptions import ExternalServiceError


class MarketDataEngine:
    def get_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for raw_symbol in symbols:
            symbol = raw_symbol.upper().strip()
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info

                price = info.get("lastPrice")
                previous_close = info.get("previousClose")
                currency = info.get("currency")

                change = None
                change_pct = None
                if price is not None and previous_close not in (None, 0):
                    change = price - previous_close
                    change_pct = (change / previous_close) * 100

                results.append(
                    {
                        "symbol": symbol,
                        "price": price,
                        "previous_close": previous_close,
                        "change": change,
                        "change_pct": change_pct,
                        "currency": currency,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "symbol": symbol,
                        "price": None,
                        "previous_close": None,
                        "change": None,
                        "change_pct": None,
                        "currency": None,
                        "error": str(exc),
                    }
                )

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
