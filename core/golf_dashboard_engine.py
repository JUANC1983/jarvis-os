from __future__ import annotations

import json
import sqlite3
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.golf_course_database import GolfCourseDatabase


# ---------------------------------------------------------------------------
# WMO Weather Interpretation Code → (description, severity)
# https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------
_WMO: Dict[int, Tuple[str, str]] = {
    0:  ("Clear sky",          "ok"),
    1:  ("Mainly clear",       "ok"),
    2:  ("Partly cloudy",      "ok"),
    3:  ("Overcast",           "ok"),
    45: ("Fog",                "warn"),
    48: ("Icy fog",            "warn"),
    51: ("Light drizzle",      "warn"),
    53: ("Drizzle",            "warn"),
    55: ("Heavy drizzle",      "warn"),
    61: ("Slight rain",        "warn"),
    63: ("Rain",               "bad"),
    65: ("Heavy rain",         "bad"),
    71: ("Slight snow",        "bad"),
    73: ("Snow",               "bad"),
    75: ("Heavy snow",         "bad"),
    77: ("Snow grains",        "warn"),
    80: ("Rain showers",       "warn"),
    81: ("Moderate showers",   "bad"),
    82: ("Violent showers",    "bad"),
    85: ("Slight snowfall",    "bad"),
    86: ("Heavy snowfall",     "bad"),
    95: ("Thunderstorm",       "bad"),
    96: ("Thunderstorm+hail",  "bad"),
    99: ("Severe thunderstorm","bad"),
}

_STATUS_MAP = {
    ("ok",   False): "optimal",   # good weather, low wind
    ("ok",   True):  "playable",  # good weather, high wind
    ("warn", False): "playable",
    ("warn", True):  "bad",
    ("bad",  False): "bad",
    ("bad",  True):  "bad",
}

# Courses to feature in the dashboard (by DB name, prioritising Colombia + prestige)
_FEATURED_COURSE_NAMES = [
    "Country Club Bogotá",
    "Club Campestre Medellín",
    "Club Campestre de Cali",
    "Augusta National",
    "St Andrews Old Course",
    "TPC Sawgrass",
]


class GolfDashboardEngine:
    """
    Lightweight dashboard layer that wires existing GolfCourseDatabase
    with real-time weather (Open-Meteo, no API key) and generates
    tee-time windows and insights.
    """

    WEATHER_CACHE_TTL_S: int = 1800   # 30 min — weather doesn't change faster
    WEATHER_TIMEOUT_S: int = 4
    STATS_FILE = Path("data/golf/player_stats.json")

    def __init__(self) -> None:
        self.db = GolfCourseDatabase()
        self._weather_cache: Dict[str, Tuple[float, Dict]] = {}  # key → (ts, payload)
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #
    def dashboard_summary(self, max_courses: int = 6) -> Dict[str, Any]:
        courses_raw = self._load_featured_courses(max_courses)

        # Fetch all weather in parallel — avoids N × RTT sequential latency
        def _enrich(c: Dict[str, Any]) -> Dict[str, Any]:
            lat = c.get("latitude")
            lon = c.get("longitude")
            weather = self._fetch_weather(lat, lon) if (lat and lon) else None
            desc, temp_c, wind_kmh, severity = self._parse_weather(weather)
            status = self._classify_status(severity, wind_kmh)
            slot = self._next_tee_slot(status)
            return {
                "name":      c.get("name", "Unknown"),
                "location":  self._location_label(c),
                "weather":   f"{desc} {temp_c}°C" if temp_c is not None else desc,
                "wind_kmh":  wind_kmh,
                "status":    status,
                "next_slot": slot,
            }

        courses_out: List[Dict[str, Any]] = [None] * len(courses_raw)  # type: ignore
        with ThreadPoolExecutor(max_workers=len(courses_raw) or 1) as pool:
            futures = {pool.submit(_enrich, c): i for i, c in enumerate(courses_raw)}
            for future in as_completed(futures, timeout=self.WEATHER_TIMEOUT_S + 2):
                idx = futures[future]
                try:
                    courses_out[idx] = future.result()
                except Exception:
                    c = courses_raw[idx]
                    courses_out[idx] = {
                        "name":      c.get("name", "Unknown"),
                        "location":  self._location_label(c),
                        "weather":   "No data",
                        "wind_kmh":  0.0,
                        "status":    "playable",
                        "next_slot": self._next_tee_slot("playable"),
                    }

        # Drop any None slots (futures that didn't complete in time)
        courses_out = [c for c in courses_out if c is not None]

        insights = self._generate_insights(courses_out)
        player   = self._player_stats()

        return {
            "courses":        courses_out,
            "insights":       insights,
            "player":         player,
            "generated_at":   datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Course loading                                                       #
    # ------------------------------------------------------------------ #
    def _load_featured_courses(self, max_courses: int) -> List[Dict[str, Any]]:
        """
        Try to load the featured list from the DB.
        Falls back to all courses ordered by name if featured names aren't found.
        """
        conn = sqlite3.connect(str(self.db.db_path))
        conn.row_factory = sqlite3.Row

        results: List[Dict[str, Any]] = []

        # Try featured names first (preserving priority order)
        for name in _FEATURED_COURSE_NAMES:
            row = conn.execute(
                "SELECT * FROM courses WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            if row:
                results.append(dict(row))
            if len(results) >= max_courses:
                break

        # If we didn't fill up, pad with other courses from the DB
        if len(results) < max_courses:
            seen = {r["name"] for r in results}
            extras = conn.execute(
                "SELECT * FROM courses WHERE latitude IS NOT NULL ORDER BY country, name"
            ).fetchall()
            for row in extras:
                if len(results) >= max_courses:
                    break
                if row["name"] not in seen:
                    results.append(dict(row))

        conn.close()
        return results

    # ------------------------------------------------------------------ #
    # Weather                                                              #
    # ------------------------------------------------------------------ #
    def _fetch_weather(self, lat: float, lon: float) -> Optional[Dict]:
        key = f"{round(lat, 2)},{round(lon, 2)}"

        with self._cache_lock:
            if key in self._weather_cache:
                ts, payload = self._weather_cache[key]
                if time.monotonic() - ts < self.WEATHER_CACHE_TTL_S:
                    return payload

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&wind_speed_unit=kmh"
            f"&timezone=auto"
        )

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "JARVIS-Golf/1.0"}
            )
            with urllib.request.urlopen(req, timeout=self.WEATHER_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            with self._cache_lock:
                self._weather_cache[key] = (time.monotonic(), data)

            return data

        except Exception:
            return None

    def _parse_weather(
        self, weather: Optional[Dict]
    ) -> Tuple[str, Optional[float], float, str]:
        """Returns (description, temp_c, wind_kmh, severity)."""
        if not weather:
            return "No data", None, 0.0, "ok"

        cw = weather.get("current_weather", {})
        code     = int(cw.get("weathercode", 0))
        temp_c   = cw.get("temperature")
        wind_kmh = float(cw.get("windspeed", 0.0))

        desc, severity = _WMO.get(code, ("Unknown", "ok"))

        if temp_c is not None:
            temp_c = round(float(temp_c), 1)

        return desc, temp_c, wind_kmh, severity

    def _classify_status(self, severity: str, wind_kmh: float) -> str:
        high_wind = wind_kmh > 35.0
        return _STATUS_MAP.get((severity, high_wind), "playable")

    # ------------------------------------------------------------------ #
    # Tee times                                                            #
    # ------------------------------------------------------------------ #
    def _next_tee_slot(self, status: str) -> str:
        """
        Returns the next available 30-min tee slot within playing hours.
        Avoids bad-weather slots when possible.
        """
        now = datetime.now()
        # Round up to the next 30-min boundary
        minutes = now.minute
        delta = (30 - (minutes % 30)) % 30 or 30
        slot = now + timedelta(minutes=delta)
        slot = slot.replace(second=0, microsecond=0)

        earliest = slot.replace(hour=7, minute=0)
        latest   = slot.replace(hour=17, minute=0)

        if slot < earliest:
            slot = earliest
        if slot > latest:
            # No more slots today
            return "No slots today"

        # If conditions are bad, suggest early morning of tomorrow
        if status == "bad":
            return "Tomorrow morning (weather)"

        return slot.strftime("%H:%M")

    # ------------------------------------------------------------------ #
    # Insights                                                             #
    # ------------------------------------------------------------------ #
    def _generate_insights(self, courses: List[Dict[str, Any]]) -> List[str]:
        insights: List[str] = []

        optimal  = [c for c in courses if c["status"] == "optimal"]
        playable = [c for c in courses if c["status"] == "playable"]
        bad      = [c for c in courses if c["status"] == "bad"]

        if optimal:
            names = ", ".join(c["name"].split()[0] for c in optimal[:2])
            insights.append(f"Optimal conditions today at {names}.")
        elif playable:
            insights.append("Playable conditions — manageable wind and cloud cover.")
        else:
            insights.append("Challenging conditions across most courses today.")

        # Wind insight
        high_wind = [c for c in courses if c.get("wind_kmh", 0) > 30]
        if high_wind:
            avg_wind = round(sum(c["wind_kmh"] for c in high_wind) / len(high_wind))
            insights.append(f"Strong winds ({avg_wind} km/h avg) — club up and flight the ball low.")
        else:
            insights.append("Wind conditions within normal range — standard game plan.")

        # Time-of-day insight
        hour = datetime.now().hour
        if 6 <= hour < 11:
            insights.append("Morning tee times available — ideal dew conditions.")
        elif 11 <= hour < 15:
            insights.append("Midday window open — expect firmer greens and more bounce.")
        elif 15 <= hour < 18:
            insights.append("Afternoon slots available — cooler temperatures for the back nine.")
        else:
            insights.append("Book tomorrow morning for the best conditions.")

        # Colombia-specific
        col_courses = [c for c in courses if "Bogotá" in c.get("location", "") or
                       "Medellín" in c.get("location", "") or "Cali" in c.get("location", "")]
        col_optimal = [c for c in col_courses if c["status"] in ("optimal", "playable")]
        if col_optimal:
            insights.append(f"{col_optimal[0]['name']} in good shape — consider booking soon.")

        return insights[:5]

    # ------------------------------------------------------------------ #
    # Player stats                                                         #
    # ------------------------------------------------------------------ #
    def _player_stats(self) -> Dict[str, Any]:
        """
        Lightweight player performance tracker.
        Reads from data/golf/player_stats.json; returns defaults if not present.
        Structured for future integrations (handicap API, shot tracking).
        """
        self.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

        if self.STATS_FILE.exists():
            try:
                data = json.loads(self.STATS_FILE.read_text(encoding="utf-8"))
                return data
            except Exception:
                pass

        # Default skeleton — ready to be populated by future rounds
        default: Dict[str, Any] = {
            "handicap_index": None,
            "rounds_logged":  0,
            "recent_scores":  [],
            "best_score":     None,
            "avg_score":      None,
            "strengths":      [],
            "areas_to_improve": ["Track a round to unlock insights"],
            "last_round":     None,
        }
        self.STATS_FILE.write_text(
            json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return default

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _location_label(course: Dict[str, Any]) -> str:
        parts = [p for p in [course.get("city"), course.get("country")] if p]
        return ", ".join(parts) if parts else course.get("region", "")

    # ------------------------------------------------------------------ #
    # Player stats write helper (for future round logging)                #
    # ------------------------------------------------------------------ #
    def log_round(
        self,
        score: int,
        course_name: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        stats = self._player_stats()
        stats["rounds_logged"] = stats.get("rounds_logged", 0) + 1
        stats["last_round"] = {
            "date":        datetime.utcnow().isoformat(),
            "course":      course_name,
            "score":       score,
            "notes":       notes,
        }

        recent = stats.get("recent_scores", [])
        recent.append(score)
        recent = recent[-10:]   # keep last 10 rounds
        stats["recent_scores"] = recent

        if recent:
            stats["best_score"] = min(recent)
            stats["avg_score"]  = round(sum(recent) / len(recent), 1)

        self.STATS_FILE.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return stats
