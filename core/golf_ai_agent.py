from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.golf_course_database import GolfCourseDatabase

try:
    from core.golf_biomechanics_engine import GolfBiomechanicsEngine
    _BIO_AVAILABLE = True
except Exception:
    _BIO_AVAILABLE = False

try:
    from core.golf_swing_vision_pro import GolfSwingVisionPro
    _VISION_AVAILABLE = True
except Exception:
    _VISION_AVAILABLE = False


class GolfAIAgent:
    """
    Master golf intelligence agent.
    Club recommendation and swing analysis work on Railway.
    Video analysis requires optional cv2/mediapipe (degrades gracefully).
    """

    def __init__(self) -> None:
        self.db = GolfCourseDatabase()
        self.bio = GolfBiomechanicsEngine() if _BIO_AVAILABLE else None
        self.vision = GolfSwingVisionPro() if _VISION_AVAILABLE else None

    # ------------------------------------------------------------------
    # Club Recommendation
    # ------------------------------------------------------------------

    def recommend_club(
        self,
        distance: float,
        wind_mph: float = 0.0,
        wind_direction: str = "neutral",
        elevation_delta_yards: float = 0.0,
        lie: str = "fairway",
        temperature_c: float = 22.0,
        player_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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

        club = self._club_from_distance(adjusted)

        return {
            "requested_distance": round(float(distance), 1),
            "adjusted_distance": round(float(adjusted), 1),
            "recommended_club": club,
            "why": [
                f"Distancia ajustada: {round(float(adjusted), 1)} yardas.",
                f"Lugar de golpe: {lie}.",
                f"Viento: {wind_direction} {wind_mph} mph.",
                "La recomendación prioriza carry útil y dispersión razonable.",
            ],
            "caddie_note": f"Con {club}, prioriza contacto sólido y target conservador.",
        }

    # ------------------------------------------------------------------
    # Swing Analysis
    # ------------------------------------------------------------------

    def analyze_swing_video(self, video_path: str, player_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.bio is None:
            analysis = {
                "status": "unavailable",
                "message": "Video biomechanics requires OpenCV. Install opencv-python to enable.",
            }
        else:
            analysis = self.bio.analyze_video(video_path)

        drills = [
            {"name": "Pause at the top drill", "goal": "Mejorar transición y secuencia",
             "how": "3 series de 8 swings pausando 1 segundo arriba"},
            {"name": "Feet together drill", "goal": "Mejorar balance y centro de contacto",
             "how": "2 series de 10 swings suaves con pies juntos"},
            {"name": "Split-hand drill", "goal": "Mejorar release y control de cara",
             "how": "2 series de 8 swings con manos separadas"},
        ]

        gym = [
            {"exercise": "Split squat",           "prescription": "3x8 por lado", "why": "Fuerza unilateral y estabilidad"},
            {"exercise": "Romanian deadlift",      "prescription": "3x6-8",        "why": "Cadena posterior y velocidad"},
            {"exercise": "Med-ball rotational throw","prescription": "4x5 por lado","why": "Potencia rotacional"},
            {"exercise": "Pallof press",           "prescription": "3x10 por lado","why": "Core anti-rotación"},
            {"exercise": "Thoracic mobility",      "prescription": "5 min diarios", "why": "Más rotación útil"},
        ]

        return {
            "status": "ok",
            "video_analysis": analysis,
            "drills": drills,
            "gym_recommendations": gym,
            "next_focus": [
                "Prioriza strike y start line antes de aumentar velocidad.",
                "Usa un mismo ángulo de cámara para comparar progreso real.",
                "No ajustes equipment antes de validar movimiento.",
            ],
        }

    def compare_swings(
        self, video_path_a: str, video_path_b: str,
        label_a: str = "before", label_b: str = "after"
    ) -> Dict[str, Any]:
        a = self.analyze_swing_video(video_path_a)
        b = self.analyze_swing_video(video_path_b)
        return {
            "status": "ok",
            "labels": {"a": label_a, "b": label_b},
            "comparison": {
                "a_takeaway": a.get("video_analysis", {}).get("advanced_review", {}).get("summary"),
                "b_takeaway": b.get("video_analysis", {}).get("advanced_review", {}).get("summary"),
            },
            "coach_takeaway": [
                "La mejora real no es solo estética; debe reflejar mejor contacto y control.",
                "Compara balance, secuencia, estabilidad y claridad del patrón de salida.",
            ],
        }

    def detect_swing_faults(self, video_path: str) -> Dict[str, Any]:
        if self.bio is None:
            return {"status": "unavailable", "message": "OpenCV required for video analysis."}
        return {"status": "ok", "fault_review": self.bio.analyze_video(video_path)}

    # ------------------------------------------------------------------
    # Fitting & Biometrics
    # ------------------------------------------------------------------

    def fitting_recommendation(self, player_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pp = player_profile or {}
        common_miss = str(pp.get("common_miss", "slice")).lower()

        recs: List[str] = []
        if common_miss in ["slice", "derecha"]:
            recs.append("Probar configuración menos castigadora en driver y revisar lie/shaft.")
            recs.append("No comprar equipo nuevo sin validar cara abierta vs. secuencia.")
        elif common_miss in ["hook", "izquierda"]:
            recs.append("Revisar lie demasiado upright, offset y grip demasiado fuerte.")

        if not recs:
            recs.append("Perfil neutro. Recomendado fitting por launch monitor y dispersión.")

        return {
            "status": "ok",
            "fitting_recommendations": recs,
            "priority_order": [
                "Driver launch/spin/strike",
                "Irons gapping + lie angle",
                "Wedges gapping y yardajes parciales",
                "Putter aim/tempo",
            ],
        }

    def biometrics_profile(self, player_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "status": "ok",
            "mobility_focus": [
                "Rotación torácica", "Cadera interna/externa", "Escápula", "Core anti-rotación",
            ],
            "power_focus": [
                "Pierna unilateral", "Rotación explosiva", "Transferencia de fuerza", "Velocidad sin perder control",
            ],
            "warning": "Si hay dolor lumbar, hombro o codo, bajar volumen y revisar técnica.",
        }

    # ------------------------------------------------------------------
    # Course Caddie & GPS
    # ------------------------------------------------------------------

    def course_caddie(self, latitude: float, longitude: float, hole_number: Optional[int] = None) -> Dict[str, Any]:
        course = self.db.nearest_course(latitude, longitude, max_km=20.0)
        if not course:
            return {
                "status": "not_found",
                "message": "No encontré un campo cercano en la base local.",
            }
        return {
            "status": "ok",
            "course": course,
            "hole_number": hole_number,
            "strategy_note": "Juega a tu dispersión, no al swing perfecto. Prioriza zona segura y yardaje medio.",
        }

    def watch_ready_payload(
        self,
        latitude: float,
        longitude: float,
        distance_front: float,
        distance_middle: float,
        distance_back: float,
        hole_number: Optional[int] = None,
        player_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        course = self.course_caddie(latitude, longitude, hole_number)
        club_mid = self.recommend_club(distance_middle, player_profile=player_profile)
        return {
            "status": "ok",
            "gps": {"latitude": latitude, "longitude": longitude},
            "course": course,
            "yardages": {"front": distance_front, "middle": distance_middle, "back": distance_back},
            "primary_recommendation": club_mid,
            "watch_note": "Payload listo para iPhone companion / Apple Watch.",
        }

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def search_courses(self, query: str, limit: int = 10) -> Dict[str, Any]:
        return {"status": "ok", "items": self.db.search_by_name(query, limit=limit)}

    def import_courses_json(self, json_path: str) -> Dict[str, Any]:
        return self.db.import_json(json_path)

    def database_stats(self) -> Dict[str, Any]:
        return self.db.stats()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _club_from_distance(self, d: float) -> str:
        if d < 90:   return "60° / Lob Wedge"
        if d < 105:  return "56° / Sand Wedge"
        if d < 118:  return "AW / Gap Wedge"
        if d < 130:  return "PW"
        if d < 142:  return "9 Iron"
        if d < 154:  return "8 Iron"
        if d < 167:  return "7 Iron"
        if d < 180:  return "6 Iron"
        if d < 193:  return "5 Iron"
        if d < 208:  return "4 Iron / Hybrid"
        if d < 228:  return "5 Wood / Strong Hybrid"
        return "3 Wood / Driver depending on hole strategy"
