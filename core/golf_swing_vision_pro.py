from __future__ import annotations

from typing import Any, Dict, List

try:
    import cv2
    import mediapipe as mp
    _CV2_AVAILABLE = True
except Exception:
    _CV2_AVAILABLE = False


class GolfSwingVisionPro:
    """
    Pose-based swing analysis using cv2 + mediapipe.
    Gracefully degrades when OpenCV/MediaPipe are unavailable (Railway default).
    """

    def __init__(self) -> None:
        self._ready = False
        if _CV2_AVAILABLE:
            try:
                self._mp_pose = mp.solutions.pose
                self._pose = self._mp_pose.Pose()
                self._ready = True
            except Exception:
                self._ready = False

    def analyze(self, video_path: str) -> Dict[str, Any]:
        if not self._ready:
            return {
                "status": "unavailable",
                "message": "Pose analysis requires OpenCV + MediaPipe. Install opencv-python and mediapipe to enable.",
                "recommendations": [
                    "Mantener inclinación de columna estable",
                    "Trabajar drills de postura",
                    "Fortalecer core",
                ],
            }

        try:
            cap = cv2.VideoCapture(video_path)
            frames: List[Any] = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            cap.release()

            posture_flags: List[str] = []
            for frame in frames[::10]:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self._pose.process(img)
                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    shoulder = landmarks[11]
                    hip = landmarks[23]
                    spine_angle = abs(shoulder.y - hip.y)
                    if spine_angle < 0.05:
                        posture_flags.append("loss_of_posture")

            faults: List[str] = []
            if posture_flags:
                faults.append("Postura perdida durante el swing")

            return {
                "status": "ok",
                "faults": faults,
                "recommendations": [
                    "Mantener inclinación de columna estable",
                    "Trabajar drills de postura",
                    "Fortalecer core",
                ],
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
