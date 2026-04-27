"""Weather Engine — OpenWeatherMap current conditions + 5-day forecast.

Falls back gracefully if OPENWEATHER_API_KEY is not set or the API is
unreachable. All public methods return dicts safe for JSON serialisation.

Cache: 10-minute per (lat, lon) pair — fine for current conditions.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

_CACHE: dict[str, dict] = {}  # key: "lat,lon" → {data, ts}
_TTL = 600.0  # 10 minutes

_WIND_DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# Beaufort-style labels for wind — useful for golf/running context
_WIND_LABEL = [
    (1,  "calm"),
    (5,  "light breeze"),
    (10, "gentle breeze"),
    (20, "moderate wind"),
    (30, "strong wind"),
    (50, "very strong wind"),
    (999,"storm"),
]


def _wind_label(ms: float) -> str:
    kmh = ms * 3.6
    for threshold, label in _WIND_LABEL:
        if kmh <= threshold:
            return label
    return "storm"


def _wind_direction(deg: float) -> str:
    return _WIND_DIRS[round(deg / 45) % 8]


def _api_key() -> Optional[str]:
    return os.getenv("OPENWEATHER_API_KEY") or os.getenv("OWM_API_KEY")


def _fetch_json(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


class WeatherEngine:
    """Fetch current weather + basic 5-day forecast for a lat/lon pair."""

    def get_current(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Return current conditions dict. Uses cache; never raises.
        Returns {"available": False} when API key is absent or call fails.
        """
        key = f"{round(lat, 2)},{round(lon, 2)}"
        now = time.monotonic()
        cached = _CACHE.get(key)
        if cached and (now - cached["ts"]) < _TTL:
            return cached["data"]

        api_key = _api_key()
        if not api_key:
            return {"available": False, "reason": "OPENWEATHER_API_KEY not configured"}

        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=es"
            )
            raw = _fetch_json(url)
            result = self._parse_current(raw)
            _CACHE[key] = {"data": result, "ts": now}
            return result
        except Exception as e:
            return {"available": False, "reason": str(e)[:80]}

    def get_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """3-day summary forecast (picks noon slot each day)."""
        api_key = _api_key()
        if not api_key:
            return {"available": False}
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=es&cnt=24"
            )
            raw = _fetch_json(url)
            return self._parse_forecast(raw)
        except Exception as e:
            return {"available": False, "reason": str(e)[:80]}

    def as_context_string(self, lat: float, lon: float) -> str:
        """Compact one-liner for LLM system prompt injection."""
        d = self.get_current(lat, lon)
        if not d.get("available", True) or not d:
            return ""
        parts = [
            f"Weather: {d.get('temp_c', '?')}°C, feels {d.get('feels_like_c', '?')}°C",
            d.get("description", ""),
            f"humidity {d.get('humidity_pct', '?')}%",
            f"wind {d.get('wind_kmh', '?')} km/h {d.get('wind_dir', '')} ({d.get('wind_label', '')})",
        ]
        if d.get("city"):
            parts.insert(0, d["city"])
        return " · ".join(p for p in parts if p)

    def golf_context(self, lat: float, lon: float) -> str:
        """Targeted golf advice string."""
        d = self.get_current(lat, lon)
        if not d.get("available", True):
            return ""
        temp    = d.get("temp_c", 20)
        wind_ms = d.get("wind_ms", 0)
        wind_kmh = round(wind_ms * 3.6, 1)
        wind_dir = d.get("wind_dir", "")
        humidity = d.get("humidity_pct", 60)

        # Ball flight notes
        notes = []
        if temp < 10:
            notes.append("cold air reduces carry ~5–8%")
        elif temp > 30:
            notes.append("hot/thin air adds ~2–3% carry")
        if wind_kmh > 15:
            notes.append(f"{wind_kmh} km/h {wind_dir} wind — adjust aim and club up/down")
        if humidity > 85:
            notes.append("high humidity softens fairways")
        if d.get("rain_mm", 0) > 0:
            notes.append("rain expected — plugged lies likely")

        base = f"{temp}°C, {wind_kmh} km/h {wind_dir}, {d.get('description','')}"
        if notes:
            base += " · " + " · ".join(notes)
        return base

    def running_context(self, lat: float, lon: float) -> str:
        """Targeted running advice string."""
        d = self.get_current(lat, lon)
        if not d.get("available", True):
            return ""
        feels = d.get("feels_like_c", 20)
        humidity = d.get("humidity_pct", 60)
        wind_kmh = round(d.get("wind_ms", 0) * 3.6, 1)
        rain = d.get("rain_mm", 0)

        advice = []
        if feels < 5:
            advice.append("very cold — wear gloves and thermal layer")
        elif feels < 12:
            advice.append("cool — light jacket recommended")
        elif feels > 28:
            advice.append("hot — slow your pace 10–20%, hydrate early")
        elif feels > 22:
            advice.append("warm — stay hydrated")

        if humidity > 80 and feels > 20:
            advice.append("high humidity increases perceived effort")
        if rain > 0:
            advice.append("rain — road may be slippery, reduce pace")
        if wind_kmh > 20:
            advice.append(f"{wind_kmh} km/h headwind possible — adjust pace out/back")

        base = f"{d.get('temp_c','?')}°C feels {feels}°C, {d.get('description','')}"
        if advice:
            base += " · " + " · ".join(advice)
        return base

    # ── Parsers ───────────────────────────────────────────────────────

    def _parse_current(self, raw: dict) -> Dict[str, Any]:
        main    = raw.get("main", {})
        wind    = raw.get("wind", {})
        weather = (raw.get("weather") or [{}])[0]
        rain    = raw.get("rain", {}).get("1h", 0) or 0
        sys_    = raw.get("sys", {})

        wind_ms  = wind.get("speed", 0)
        wind_deg = wind.get("deg", 0)

        return {
            "available":     True,
            "city":          raw.get("name", ""),
            "country":       sys_.get("country", ""),
            "temp_c":        round(main.get("temp", 0), 1),
            "feels_like_c":  round(main.get("feels_like", 0), 1),
            "temp_min_c":    round(main.get("temp_min", 0), 1),
            "temp_max_c":    round(main.get("temp_max", 0), 1),
            "humidity_pct":  main.get("humidity", 0),
            "pressure_hpa":  main.get("pressure", 1013),
            "description":   weather.get("description", ""),
            "icon":          weather.get("icon", ""),
            "wind_ms":       round(wind_ms, 1),
            "wind_kmh":      round(wind_ms * 3.6, 1),
            "wind_dir":      _wind_direction(wind_deg),
            "wind_deg":      wind_deg,
            "wind_label":    _wind_label(wind_ms),
            "rain_mm":       rain,
            "visibility_km": round(raw.get("visibility", 10000) / 1000, 1),
            "clouds_pct":    raw.get("clouds", {}).get("all", 0),
            "timestamp":     raw.get("dt", 0),
        }

    def _parse_forecast(self, raw: dict) -> Dict[str, Any]:
        days: list = []
        seen: set  = set()
        for item in raw.get("list", []):
            date = item["dt_txt"][:10]
            hour = int(item["dt_txt"][11:13])
            if date in seen:
                continue
            if hour < 10:
                continue  # prefer midday slot
            seen.add(date)
            main    = item.get("main", {})
            weather = (item.get("weather") or [{}])[0]
            days.append({
                "date":        date,
                "temp_c":      round(main.get("temp", 0), 1),
                "feels_like":  round(main.get("feels_like", 0), 1),
                "description": weather.get("description", ""),
                "icon":        weather.get("icon", ""),
                "rain_mm":     item.get("rain", {}).get("3h", 0) or 0,
                "wind_kmh":    round(item.get("wind", {}).get("speed", 0) * 3.6, 1),
            })
            if len(days) >= 4:
                break
        return {"available": True, "forecast": days}


# Module-level singleton
weather_engine = WeatherEngine()
