from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except Exception:
    _CV2_AVAILABLE = False

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_LIB = True
except Exception:
    _OPENAI_LIB = False


_UNAVAILABLE_MSG = "Video biomechanics requires OpenCV. Install opencv-python to enable frame analysis."


class GolfBiomechanicsEngine:
    """
    Frame-based swing quality analysis.
    Gracefully degrades to heuristic-only when cv2 is unavailable.
    """

    def __init__(self) -> None:
        self._cv2_ready = _CV2_AVAILABLE
        self.client = None
        if _OPENAI_LIB and os.getenv("OPENAI_API_KEY"):
            self.client = _OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sample_frames(self, video_path: str, max_frames: int = 8) -> List[Any]:
        if not self._cv2_ready:
            return []

        path = Path(video_path)
        if not path.exists():
            return []

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            total_frames = 120

        indices = np.linspace(0, max(total_frames - 1, 1), num=max_frames, dtype=int)
        frames: List[Any] = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)

        cap.release()
        return frames

    def analyze_quality(self, frames: List[Any]) -> Dict[str, Any]:
        if not frames:
            return {"status": "error", "message": "No frames"}
        if not self._cv2_ready:
            return {"status": "unavailable", "message": _UNAVAILABLE_MSG}

        brightness: List[float] = []
        edge_density: List[float] = []

        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness.append(float(np.mean(gray)))
            edges = cv2.Canny(gray, 80, 180)
            edge_density.append(float(np.mean(edges > 0)))

        flags: List[str] = []
        if np.mean(brightness) < 35:
            flags.append("video_dark")
        if np.mean(edge_density) < 0.02:
            flags.append("low_detail_video")

        return {
            "status": "ok",
            "flags": flags,
            "avg_brightness": round(float(np.mean(brightness)), 2),
            "avg_edge_density": round(float(np.mean(edge_density)), 4),
        }

    def heuristic_faults(self, frames: List[Any]) -> Dict[str, Any]:
        quality = self.analyze_quality(frames)
        simple_faults: List[str] = []

        if quality.get("status") == "unavailable":
            return {
                "status": "unavailable",
                "message": _UNAVAILABLE_MSG,
                "coach_baseline": _BASELINE_TIPS,
            }

        if "video_dark" in quality.get("flags", []):
            simple_faults.append("El video está oscuro; puede ocultar errores reales.")
        if "low_detail_video" in quality.get("flags", []):
            simple_faults.append("El video tiene poco detalle; conviene grabar más cerca y con mejor luz.")

        return {
            "status": "ok",
            "quality": quality,
            "simple_faults": simple_faults,
            "coach_baseline": _BASELINE_TIPS,
        }

    def llm_swing_analysis(self, frames: List[Any]) -> Dict[str, Any]:
        if not self.client:
            return {
                "status": "fallback",
                "summary": "OPENAI_API_KEY no configurada. Solo análisis heurístico disponible.",
            }
        if not self._cv2_ready:
            return {"status": "unavailable", "summary": _UNAVAILABLE_MSG}

        content: List[Any] = [{
            "type": "text",
            "text": (
                "Actúa como coach elite de golf, biomecánica y mejora del rendimiento. "
                "Analiza el swing usando estos frames. Habla en español, corto y claro. "
                "No inventes números de launch monitor. "
                "Evalúa setup, backswing, top, transición, downswing, impacto, release, finish, balance, secuencia, "
                "y explica errores fáciles de entender. "
                "Devuelve: 1) qué está mal 2) qué está bien 3) drills 4) ejercicios de gimnasio para más distancia."
            ),
        }]

        for frame in frames[:6]:
            ok, buf = cv2.imencode(".jpg", frame)
            if ok:
                b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                temperature=0.2,
                max_tokens=900,
            )
            return {"status": "ok", "summary": (resp.choices[0].message.content or "").strip()}
        except Exception as exc:
            return {"status": "error", "summary": f"Falló análisis avanzado: {exc}"}

    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        if not self._cv2_ready:
            return {
                "status": "unavailable",
                "video_path": video_path,
                "message": _UNAVAILABLE_MSG,
                "heuristics": {"coach_baseline": _BASELINE_TIPS},
                "advanced_review": {"status": "unavailable", "summary": _UNAVAILABLE_MSG},
                "easy_takeaways": _EASY_TAKEAWAYS,
            }

        frames = self.sample_frames(video_path, max_frames=10)
        if not frames:
            return {"status": "error", "message": "No se pudieron extraer frames del video."}

        heuristics = self.heuristic_faults(frames)
        advanced = self.llm_swing_analysis(frames)

        return {
            "status": "ok",
            "video_path": video_path,
            "heuristics": heuristics,
            "advanced_review": advanced,
            "easy_takeaways": _EASY_TAKEAWAYS,
        }


# ------------------------------------------------------------------
# Shared constants
# ------------------------------------------------------------------

_BASELINE_TIPS = [
    "Revisar balance final.",
    "Revisar secuencia antes de culpar solo a las manos.",
    "Validar control de cara y start line.",
]

_EASY_TAKEAWAYS = [
    "Busca mejor contacto antes que más fuerza.",
    "Si el finish no es estable, normalmente hubo un problema antes en la secuencia.",
    "No cambies fitting antes de validar cara, path y strike.",
]
