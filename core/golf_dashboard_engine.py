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
# Lazy-import guards for heavy deps (cv2 is broken in this env; these
# activate automatically once cv2 is repaired without any code changes)
# ---------------------------------------------------------------------------
try:
    from core.golf_ai_agent import GolfAIAgent as _GolfAIAgent
    _AGENT_AVAILABLE = True
except Exception:
    _GolfAIAgent = None  # type: ignore
    _AGENT_AVAILABLE = False

try:
    from core.golf_biomechanics_engine import GolfBiomechanicsEngine as _BiomechEngine
    _BIOMECH_AVAILABLE = True
except Exception:
    _BiomechEngine = None  # type: ignore
    _BIOMECH_AVAILABLE = False


# ---------------------------------------------------------------------------
# WMO Weather Interpretation Code → (description, severity)
# https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------
_WMO: Dict[int, Tuple[str, str]] = {
    0:  ("Clear sky",           "ok"),
    1:  ("Mainly clear",        "ok"),
    2:  ("Partly cloudy",       "ok"),
    3:  ("Overcast",            "ok"),
    45: ("Fog",                 "warn"),
    48: ("Icy fog",             "warn"),
    51: ("Light drizzle",       "warn"),
    53: ("Drizzle",             "warn"),
    55: ("Heavy drizzle",       "warn"),
    61: ("Slight rain",         "warn"),
    63: ("Rain",                "bad"),
    65: ("Heavy rain",          "bad"),
    71: ("Slight snow",         "bad"),
    73: ("Snow",                "bad"),
    75: ("Heavy snow",          "bad"),
    77: ("Snow grains",         "warn"),
    80: ("Rain showers",        "warn"),
    81: ("Moderate showers",    "bad"),
    82: ("Violent showers",     "bad"),
    85: ("Slight snowfall",     "bad"),
    86: ("Heavy snowfall",      "bad"),
    95: ("Thunderstorm",        "bad"),
    96: ("Thunderstorm+hail",   "bad"),
    99: ("Severe thunderstorm", "bad"),
}

_STATUS_MAP: Dict[Tuple[str, bool], str] = {
    ("ok",   False): "optimal",
    ("ok",   True):  "playable",
    ("warn", False): "playable",
    ("warn", True):  "bad",
    ("bad",  False): "bad",
    ("bad",  True):  "bad",
}

# Featured courses in priority order (Colombia first — owner's home country)
_FEATURED_COURSE_NAMES: List[str] = [
    "Country Club Bogotá",
    "Club Campestre Medellín",
    "Club Campestre de Cali",
    "Augusta National",
    "St Andrews Old Course",
    "TPC Sawgrass",
]

# Known altitude per course name (metres above sea level)
# Used for carry-distance adjustment insights
_COURSE_ALTITUDE_M: Dict[str, int] = {
    "Country Club Bogotá":    2600,
    "Club Campestre Medellín": 1495,
    "Club Campestre de Cali":   995,
    "Augusta National":          80,
    "St Andrews Old Course":     10,
    "TPC Sawgrass":               5,
    "Pebble Beach Golf Links":    0,
    "Valderrama":                80,
    "Le Golf National":          80,
}

# Club distance table — replicates GolfAIAgent._club_from_distance
# kept here so play_strategy works even when GolfAIAgent can't be imported
_CLUB_TABLE: List[Tuple[float, str]] = [
    (90,  "Lob Wedge (60°)"),
    (105, "Sand Wedge (56°)"),
    (118, "Gap Wedge (AW)"),
    (130, "PW"),
    (142, "9-Iron"),
    (154, "8-Iron"),
    (167, "7-Iron"),
    (180, "6-Iron"),
    (193, "5-Iron"),
    (208, "4-Iron / Hybrid"),
    (228, "5-Wood / Strong Hybrid"),
]


def _club_from_distance(yards: float) -> str:
    for threshold, club in _CLUB_TABLE:
        if yards < threshold:
            return club
    return "3-Wood / Driver"


class GolfDashboardEngine:
    """
    Premium lifestyle + performance intelligence module.

    Wires:
      - GolfCourseDatabase  (source of truth — 23 real courses)
      - Open-Meteo API      (real-time weather, no key required)
      - GolfAIAgent         (play strategy — lazy, activates when cv2 is fixed)
      - GolfBiomechanicsEngine (swing feedback — lazy, activates when cv2 is fixed)
      - Player stats JSON   (round tracking, handicap, performance trends)
    """

    WEATHER_CACHE_TTL_S: int = 1800   # 30 min — weather doesn't change meaningfully faster
    WEATHER_TIMEOUT_S:   int = 4      # per-call HTTP timeout
    POOL_WALL_CLOCK_S:   int = 6      # total parallel budget
    STATS_FILE = Path("data/golf/player_stats.json")

    def __init__(self) -> None:
        self.db = GolfCourseDatabase()
        self._weather_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()

        # Instantiate heavy engines only once, guarded
        self._agent: Optional[Any] = _GolfAIAgent() if _AGENT_AVAILABLE else None
        self._bio:   Optional[Any] = _BiomechEngine() if _BIOMECH_AVAILABLE else None

    # ------------------------------------------------------------------ #
    # Public — dashboard summary                                           #
    # ------------------------------------------------------------------ #
    def dashboard_summary(self, max_courses: int = 6) -> Dict[str, Any]:
        courses_raw = self._load_featured_courses(max_courses)
        n = len(courses_raw)
        courses_out: List[Optional[Dict[str, Any]]] = [None] * n

        def _enrich(idx: int, c: Dict[str, Any]) -> None:
            lat = c.get("latitude")
            lon = c.get("longitude")
            weather = self._fetch_weather(lat, lon) if (lat and lon) else None
            desc, temp_c, wind_kmh, severity = self._parse_weather(weather)
            status = self._classify_status(severity, wind_kmh)
            slot   = self._next_tee_slot(status)
            name   = c.get("name", "Unknown")

            strategy = self._play_strategy(name, wind_kmh, temp_c, status)

            courses_out[idx] = {
                "name":          name,
                "location":      self._location_label(c),
                "weather":       f"{desc} {round(temp_c, 1)}°C" if temp_c is not None else desc,
                "wind_kmh":      wind_kmh,
                "status":        status,
                "next_slot":     slot,
                "play_strategy": strategy,
            }

        with ThreadPoolExecutor(max_workers=max(n, 1)) as pool:
            futures = [pool.submit(_enrich, i, c) for i, c in enumerate(courses_raw)]
            # Wait up to wall-clock budget; each _fetch_weather has its own timeout
            done, _ = __import__("concurrent.futures", fromlist=["wait"]).wait(
                futures, timeout=self.POOL_WALL_CLOCK_S
            )

        # Fill any slots that didn't complete in time with a safe fallback
        for i, c in enumerate(courses_raw):
            if courses_out[i] is None:
                courses_out[i] = {
                    "name":          c.get("name", "Unknown"),
                    "location":      self._location_label(c),
                    "weather":       "Weather unavailable",
                    "wind_kmh":      0.0,
                    "status":        "playable",
                    "next_slot":     self._next_tee_slot("playable"),
                    "play_strategy": "Check local conditions before teeing off.",
                }

        courses_final: List[Dict[str, Any]] = [c for c in courses_out if c is not None]

        insights = self._generate_insights(courses_final)
        player   = self._player_summary()

        return {
            "courses":      courses_final,
            "insights":     insights,
            "player":       player,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Course loading                                                       #
    # ------------------------------------------------------------------ #
    def _load_featured_courses(self, max_courses: int) -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(str(self.db.db_path))
            conn.row_factory = sqlite3.Row
            results: List[Dict[str, Any]] = []

            for name in _FEATURED_COURSE_NAMES:
                if len(results) >= max_courses:
                    break
                row = conn.execute(
                    "SELECT * FROM courses WHERE name = ? LIMIT 1", (name,)
                ).fetchone()
                if row:
                    results.append(dict(row))

            if len(results) < max_courses:
                seen = {r["name"] for r in results}
                for row in conn.execute(
                    "SELECT * FROM courses WHERE latitude IS NOT NULL ORDER BY country, name"
                ).fetchall():
                    if len(results) >= max_courses:
                        break
                    if row["name"] not in seen:
                        results.append(dict(row))

            conn.close()
            return results
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Weather                                                              #
    # ------------------------------------------------------------------ #
    def _fetch_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
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
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Golf/1.0"})
            with urllib.request.urlopen(req, timeout=self.WEATHER_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            with self._cache_lock:
                self._weather_cache[key] = (time.monotonic(), data)
            return data
        except Exception:
            return None

    def _parse_weather(
        self, weather: Optional[Dict[str, Any]]
    ) -> Tuple[str, Optional[float], float, str]:
        """Returns (description, temp_c, wind_kmh, severity)."""
        if not weather:
            return "Weather unavailable", None, 0.0, "ok"
        cw       = weather.get("current_weather", {})
        code     = int(cw.get("weathercode", 0))
        temp_c   = cw.get("temperature")
        wind_kmh = float(cw.get("windspeed", 0.0))
        desc, severity = _WMO.get(code, ("Unknown conditions", "ok"))
        if temp_c is not None:
            temp_c = float(temp_c)
        return desc, temp_c, wind_kmh, severity

    def _classify_status(self, severity: str, wind_kmh: float) -> str:
        return _STATUS_MAP.get((severity, wind_kmh > 35.0), "playable")

    # ------------------------------------------------------------------ #
    # Tee slots                                                            #
    # ------------------------------------------------------------------ #
    def _next_tee_slot(self, status: str) -> str:
        now   = datetime.now()
        delta = (30 - (now.minute % 30)) % 30 or 30
        slot  = (now + timedelta(minutes=delta)).replace(second=0, microsecond=0)

        if slot.hour < 7:
            slot = slot.replace(hour=7, minute=0)
        if slot.hour >= 17:
            return "Tomorrow 07:00"
        if status == "bad":
            return "Tomorrow 07:00 (weather)"
        return slot.strftime("%H:%M")

    # ------------------------------------------------------------------ #
    # Play strategy — wires GolfAIAgent when available                    #
    # ------------------------------------------------------------------ #
    def _play_strategy(
        self,
        course_name: str,
        wind_kmh: float,
        temp_c: Optional[float],
        status: str,
    ) -> str:
        """
        Returns a short, actionable strategy line for this course.
        Uses GolfAIAgent when available; falls back to wind+altitude logic.
        """
        # Attempt to use GolfAIAgent.recommend_club for a concrete suggestion
        if self._agent is not None:
            try:
                # Mid-iron reference distance (150 yd) adjusted for wind
                wind_mph = round(wind_kmh / 1.609, 1)
                wind_dir = "headwind" if wind_kmh > 20 else "neutral"
                result = self._agent.recommend_club(
                    distance=150,
                    wind_mph=wind_mph,
                    wind_direction=wind_dir,
                    lie="fairway",
                    temperature_c=temp_c or 20.0,
                )
                club = result.get("recommended_club", "7-Iron")
                adj  = result.get("adjusted_distance", 150)
                return f"{club} plays to ~{adj} yds. {result.get('why', [''])[0]}"
            except Exception:
                pass

        # --- Fallback: derive strategy from real weather + altitude data ---
        alt_m = _COURSE_ALTITUDE_M.get(course_name, 0)
        carry_pct = round(alt_m / 1000 * 8, 0)  # ~8% per 1000m

        parts: List[str] = []

        if status == "bad":
            parts.append("Delay round — poor conditions.")
            return " ".join(parts)

        # Wind adjustment
        if wind_kmh > 35:
            # High wind: club up 2, flight low
            ref_adj = 150 + (wind_kmh - 20) * 0.9  # headwind carry penalty
            club = _club_from_distance(ref_adj)
            parts.append(f"Wind {round(wind_kmh)} km/h — play {club}, flight low and accept less distance.")
        elif wind_kmh > 20:
            parts.append(f"Moderate wind {round(wind_kmh)} km/h — club up one, commit to target.")
        else:
            parts.append("Calm conditions — play standard distances.")

        # Altitude carry bonus
        if carry_pct >= 8:
            parts.append(f"At {alt_m}m elevation, carry runs +{int(carry_pct)}% — club down one.")
        elif carry_pct >= 3:
            parts.append(f"Slight altitude bonus (+{int(carry_pct)}%) — minor club adjustment.")

        # Temperature note
        if temp_c is not None and temp_c < 10:
            parts.append("Cold air reduces ball compression — add 5–8 yds.")
        elif temp_c is not None and temp_c > 30:
            parts.append("Heat and humidity — ball carries slightly further, greens firmer.")

        return " ".join(parts) or "Standard game plan."

    # ------------------------------------------------------------------ #
    # Insights — data-driven, course-specific                             #
    # ------------------------------------------------------------------ #
    def _generate_insights(self, courses: List[Dict[str, Any]]) -> List[str]:
        insights: List[str] = []

        # 1. Best course right now
        optimal  = [c for c in courses if c["status"] == "optimal"]
        bad      = [c for c in courses if c["status"] == "bad"]

        if optimal:
            best = optimal[0]
            alt  = _COURSE_ALTITUDE_M.get(best["name"], 0)
            if alt > 1000:
                insights.append(
                    f"{best['name']} is optimal — altitude {alt}m adds +{int(alt/1000*8)}% carry. Club down one."
                )
            else:
                temp_part = f" at {best['weather'].split()[-1]}" if best.get("weather") != "Weather unavailable" else ""
                insights.append(f"{best['name']} is in optimal condition{temp_part}. Best window today.")
        elif bad and len(bad) == len(courses):
            insights.append("All tracked courses have adverse conditions — reschedule for tomorrow morning.")

        # 2. Wind-specific, course-named insight
        windy = sorted(
            [c for c in courses if c.get("wind_kmh", 0) > 25],
            key=lambda x: x["wind_kmh"], reverse=True
        )
        if windy:
            c = windy[0]
            kmh = round(c["wind_kmh"])
            insights.append(
                f"{c['name']}: {kmh} km/h winds — favor low ball flight, bump-and-run where possible."
            )

        # 3. Altitude carry insight for Colombian courses
        col_courses = [
            c for c in courses
            if any(loc in c.get("location", "") for loc in ("Bogotá", "Medellín", "Cali", "Colombia"))
        ]
        for cc in col_courses[:1]:
            alt = _COURSE_ALTITUDE_M.get(cc["name"], 0)
            if alt > 500:
                carry_gain = int(alt / 1000 * 8)
                insights.append(
                    f"{cc['name']} sits at {alt}m — expect +{carry_gain}% carry. "
                    f"Your 7-iron plays like a 6-iron here."
                )

        # 4. Time-of-day tee window
        hour = datetime.now().hour
        playable = [c for c in courses if c["status"] in ("optimal", "playable")]
        if playable:
            if 6 <= hour < 11:
                insights.append(
                    "Morning window open — cooler air, dew on greens, putts run truer. Book now."
                )
            elif 11 <= hour < 15:
                insights.append(
                    "Midday conditions: expect firm greens and more bounce. Aim short and let it release."
                )
            elif 15 <= hour < 18:
                insights.append(
                    "Afternoon slot available — temperatures dropping, ideal for 9-hole sprint."
                )
            else:
                insights.append("No viable slots left today — plan for an early morning tee time tomorrow.")

        # 5. Player performance context (if rounds exist)
        try:
            stats = self._load_player_stats()
            if stats.get("rounds_logged", 0) >= 3 and stats.get("avg_score"):
                avg = stats["avg_score"]
                best_s = stats.get("best_score")
                insights.append(
                    f"Your avg score is {avg}. Best round: {best_s}. "
                    f"Focus on {stats.get('areas_to_improve', ['consistency'])[0].lower()}."
                )
        except Exception:
            pass

        return insights[:5]

    # ------------------------------------------------------------------ #
    # Player — wires GolfBiomechanicsEngine when available               #
    # ------------------------------------------------------------------ #
    def _player_summary(self) -> Dict[str, Any]:
        stats = self._load_player_stats()

        swing_feedback     = "Upload a swing video to unlock biomechanics analysis."
        swing_recommendation = "Log your first round to get personalised coaching."

        # Attempt biomechanics engine (only meaningful when a recent video exists)
        if self._bio is not None:
            try:
                # heuristic_faults needs frames; without a video we use coach_baseline
                fallback = self._bio.heuristic_faults([])
                baselines = fallback.get("coach_baseline", [])
                if baselines:
                    swing_feedback = baselines[0]
                    swing_recommendation = baselines[1] if len(baselines) > 1 else swing_recommendation
            except Exception:
                pass

        # Derive recommendation from logged round data when available
        rounds = stats.get("rounds_logged", 0)
        recent = stats.get("recent_scores", [])
        if rounds >= 1 and recent:
            trend = recent[-1] - recent[0] if len(recent) >= 2 else 0
            if trend < 0:
                swing_recommendation = f"Scores improving by {abs(trend)} shots over last {len(recent)} rounds. Stay consistent."
            elif trend > 0:
                swing_recommendation = f"Scores up {trend} shots recently. Review pre-shot routine and course management."
            else:
                swing_recommendation = "Scores stable. Target greens in regulation to break through."

        areas = stats.get("areas_to_improve", [])
        if areas and areas[0] != "Track a round to unlock insights":
            swing_feedback = f"Focus area: {areas[0]}."

        return {
            "handicap_index":    stats.get("handicap_index"),
            "rounds_logged":     stats.get("rounds_logged", 0),
            "avg_score":         stats.get("avg_score"),
            "best_score":        stats.get("best_score"),
            "last_round":        stats.get("last_round"),
            "swing_feedback":    swing_feedback,
            "recommendation":    swing_recommendation,
            "biomech_available": self._bio is not None,
        }

    # ------------------------------------------------------------------ #
    # Public: Caddie + Search                                             #
    # ------------------------------------------------------------------ #
    def caddie(
        self,
        distance: float,
        wind_mph: float = 0.0,
        wind_direction: str = "neutral",
        elevation_delta_yards: float = 0.0,
        lie: str = "fairway",
        temperature_c: float = 22.0,
    ) -> Dict[str, Any]:
        """Club recommendation. Uses GolfAIAgent when available; pure-math fallback otherwise."""
        if self._agent is not None:
            try:
                return self._agent.recommend_club(
                    distance=distance,
                    wind_mph=wind_mph,
                    wind_direction=wind_direction,
                    elevation_delta_yards=elevation_delta_yards,
                    lie=lie,
                    temperature_c=temperature_c,
                )
            except Exception:
                pass
        # Pure-math fallback — always works
        adjusted = float(distance)
        wd = (wind_direction or "neutral").lower()
        if wd in ["headwind", "contra", "en contra"]:
            adjusted += float(wind_mph) * 0.9
        elif wd in ["tailwind", "a favor", "favor"]:
            adjusted -= float(wind_mph) * 0.6
        elif wd in ["crosswind", "cross", "lateral"]:
            adjusted += float(wind_mph) * 0.15
        adjusted += float(elevation_delta_yards)
        if lie.lower() in ["rough", "thick_rough"]:
            adjusted += 5
        elif lie.lower() in ["bunker", "fairway_bunker"]:
            adjusted += 10
        club = _club_from_distance(adjusted)
        return {
            "requested_distance": round(float(distance), 1),
            "adjusted_distance": round(float(adjusted), 1),
            "recommended_club": club,
            "why": [f"Adjusted distance: {round(float(adjusted), 1)} yds.", f"Lie: {lie}.", f"Wind: {wind_direction} {wind_mph} mph."],
            "caddie_note": f"With {club}, prioritize solid contact and conservative target.",
        }

    def search_courses(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.db.search_by_name(query, limit=limit)

    def get_profile(self) -> Dict[str, Any]:
        return self._load_player_stats()

    # ------------------------------------------------------------------ #
    # Player stats persistence                                            #
    # ------------------------------------------------------------------ #
    def _load_player_stats(self) -> Dict[str, Any]:
        self.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if self.STATS_FILE.exists():
            try:
                return json.loads(self.STATS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        default: Dict[str, Any] = {
            "handicap_index":   None,
            "rounds_logged":    0,
            "recent_scores":    [],
            "best_score":       None,
            "avg_score":        None,
            "strengths":        [],
            "areas_to_improve": ["Track a round to unlock insights"],
            "last_round":       None,
        }
        self.STATS_FILE.write_text(
            json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return default

    # kept as public alias for backward compat
    def _player_stats(self) -> Dict[str, Any]:
        return self._load_player_stats()

    def log_round(self, score: int, course_name: str, notes: str = "") -> Dict[str, Any]:
        stats = self._load_player_stats()
        stats["rounds_logged"] = stats.get("rounds_logged", 0) + 1
        stats["last_round"] = {
            "date":   datetime.utcnow().isoformat(),
            "course": course_name,
            "score":  score,
            "notes":  notes,
        }
        recent = stats.get("recent_scores", [])
        recent.append(score)
        recent = recent[-10:]
        stats["recent_scores"] = recent
        stats["best_score"] = min(recent)
        stats["avg_score"]  = round(sum(recent) / len(recent), 1)
        self.STATS_FILE.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return stats

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _location_label(course: Dict[str, Any]) -> str:
        parts = [p for p in [course.get("city"), course.get("country")] if p]
        return ", ".join(parts) if parts else course.get("region", "")
