from __future__ import annotations

import hashlib
import json
import math
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# MediaPipe Pose landmark indices
_L: Dict[str, int] = {
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13,    "right_elbow": 14,
    "left_wrist": 15,    "right_wrist": 16,
    "left_hip": 23,      "right_hip": 24,
    "left_knee": 25,     "right_knee": 26,
    "left_ankle": 27,    "right_ankle": 28,
}

_MAX_SWINGS  = 50
_KEEP_SWINGS = 40


# ── geometry helpers ─────────────────────────────────────────────────

def _pt(lms: List[Dict], name: str) -> Optional[Dict]:
    idx = _L.get(name)
    if idx is None or idx >= len(lms):
        return None
    p = lms[idx]
    return p if p.get("visibility", 1.0) > 0.25 else None


def _vec(a: Dict, b: Dict) -> Tuple[float, float, float]:
    return (b["x"] - a["x"], b["y"] - a["y"], b.get("z", 0) - a.get("z", 0))


def _angle_deg(v1: Tuple, v2: Tuple) -> float:
    dot = sum(x * y for x, y in zip(v1, v2))
    m1  = math.sqrt(sum(x ** 2 for x in v1)) or 1e-9
    m2  = math.sqrt(sum(x ** 2 for x in v2)) or 1e-9
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (m1 * m2)))))


def _mid(a: Dict, b: Dict) -> Dict:
    return {
        "x": (a["x"] + b["x"]) / 2,
        "y": (a["y"] + b["y"]) / 2,
        "z": (a.get("z", 0) + b.get("z", 0)) / 2,
    }


# ── main engine ──────────────────────────────────────────────────────

class GolfVisionEngine:
    """
    Processes MediaPipe pose landmark arrays delivered from the browser.
    Computes golf-specific biomechanics, swing phases, and coaching tips.
    Persists swing history per user.
    """

    def __init__(self, file_path: str, user_id: str = "owner") -> None:
        self._path    = Path(file_path)
        self._user_id = user_id
        self._lock    = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({"swings": []})

    # ── frame analysis ────────────────────────────────────────────────

    def analyze_frame(self, landmarks: List[Dict]) -> Dict[str, Any]:
        bio   = self.compute_biomechanics(landmarks)
        phase = self._phase_single(landmarks)
        tips  = self._rule_tips(bio)
        return {
            "status":       "ok",
            "biomechanics": bio,
            "phase":        phase,
            "tips":         tips,
            "timestamp":    datetime.utcnow().isoformat(),
        }

    def compute_biomechanics(self, lms: List[Dict]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        ls = _pt(lms, "left_shoulder");  rs = _pt(lms, "right_shoulder")
        lh = _pt(lms, "left_hip");       rh = _pt(lms, "right_hip")
        lk = _pt(lms, "left_knee");      rk = _pt(lms, "right_knee")
        la = _pt(lms, "left_ankle");     ra = _pt(lms, "right_ankle")
        le = _pt(lms, "left_elbow");     lw = _pt(lms, "left_wrist")

        # Spine angle — forward tilt from vertical
        if ls and rs and lh and rh:
            mid_s = _mid(ls, rs)
            mid_h = _mid(lh, rh)
            spine = _vec(mid_h, mid_s)
            out["spine_angle"] = round(_angle_deg(spine, (0, -1, 0)), 1)

        # Shoulder & hip rotation proxy (z-spread × 100)
        if ls and rs:
            out["shoulder_turn"] = round(abs(ls.get("z", 0) - rs.get("z", 0)) * 100, 1)
        if lh and rh:
            out["hip_turn"] = round(abs(lh.get("z", 0) - rh.get("z", 0)) * 100, 1)

        # X-factor (hip–shoulder separation)
        if "shoulder_turn" in out and "hip_turn" in out:
            out["x_factor"] = round(abs(out["shoulder_turn"] - out["hip_turn"]), 1)

        # Lead knee flex (left knee for right-handed golfer)
        if lh and lk and la:
            out["lead_knee_flex"] = round(_angle_deg(_vec(lk, lh), _vec(lk, la)), 1)

        # Trail knee flex
        if rh and rk and ra:
            out["trail_knee_flex"] = round(_angle_deg(_vec(rk, rh), _vec(rk, ra)), 1)

        # Lead arm straightness (left elbow angle)
        if ls and le and lw:
            out["lead_arm_angle"] = round(_angle_deg(_vec(le, ls), _vec(le, lw)), 1)

        # Lead wrist height relative to lead shoulder (negative = wrist above shoulder)
        if lw and ls:
            out["lead_wrist_height"] = round(ls["y"] - lw["y"], 3)

        return out

    # ── swing sequence analysis ───────────────────────────────────────

    def analyze_swing_sequence(
        self,
        frames: List[Dict],
        club:   str   = "unknown",
        fps:    float = 30.0,
    ) -> Dict[str, Any]:
        if not frames:
            return {"status": "error", "error": "No frames provided"}

        bio_seq: List[Dict] = []
        phases:  List[str]  = []

        for f in frames:
            lms = f.get("landmarks", [])
            if lms:
                bio_seq.append(self.compute_biomechanics(lms))
                phases.append(self._phase_single(lms))

        agg     = self._aggregate_bio(bio_seq)
        tempo   = self._estimate_tempo(frames)
        coaching = self._swing_coaching(agg, tempo)
        score   = self._swing_score(agg, tempo)

        analysis = {
            "status":       "ok",
            "club":         club,
            "frame_count":  len(frames),
            "duration_s":   round(len(frames) / max(fps, 1), 2),
            "tempo_ratio":  tempo,
            "phases":       phases,
            "biomechanics": agg,
            "coaching":     coaching,
            "score":        score,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Auto-persist
        self.save_swing(analysis)
        return analysis

    # ── history & drills ──────────────────────────────────────────────

    def save_swing(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "id": self._gen_id(),
            "ts": datetime.utcnow().isoformat(),
            **{k: v for k, v in analysis.items() if k not in ("frames",)},
        }
        with self._lock:
            data   = self._read()
            swings = data.get("swings", [])
            swings.append(entry)
            if len(swings) > _MAX_SWINGS:
                swings = swings[-_KEEP_SWINGS:]
            data["swings"] = swings
            self._write(data)
        return entry

    def get_history(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        data   = self._read()
        swings = list(reversed(data.get("swings", [])))
        return {
            "total":  len(swings),
            "items":  swings[offset: offset + limit],
            "offset": offset,
            "limit":  limit,
        }

    def get_drills(self, last_analysis: Optional[Dict] = None) -> List[Dict]:
        all_drills = [
            {"id": "alignment",     "name": "Alignment Stick Drill",    "focus": "setup",
             "description": "Place two alignment sticks on the ground — one for ball-target line, one for foot line. Practice address position for 5 minutes.",
             "duration_min": 5},
            {"id": "shoulder_turn", "name": "Shoulder Turn Drill",       "focus": "rotation",
             "description": "Cross arms over chest. Rotate shoulders fully while keeping lower body quiet. Feel the separation between upper and lower body.",
             "duration_min": 5},
            {"id": "hip_bump",      "name": "Hip Bump & Clear Drill",    "focus": "downswing",
             "description": "Practise initiating the downswing with a lateral left hip bump toward the target before the arms start down. Promotes proper sequencing.",
             "duration_min": 5},
            {"id": "impact_bag",    "name": "Impact Bag Training",       "focus": "impact",
             "description": "Hit an impact bag at slow speed focusing on hands-ahead position and a flat left wrist at impact. 20 reps per session.",
             "duration_min": 10},
            {"id": "tempo",         "name": "3:1 Tempo Drill",           "focus": "tempo",
             "description": "Count 1-2-3 on backswing, 1 on downswing. Use a metronome at 60 BPM. Builds a consistent, tour-average rhythm.",
             "duration_min": 10},
            {"id": "weight_shift",  "name": "Step Drill",                "focus": "weight_transfer",
             "description": "Start with feet together, step forward with the lead foot as the downswing begins. Exaggerates correct weight transfer.",
             "duration_min": 7},
            {"id": "l_to_l",        "name": "L-to-L Drill",             "focus": "wrist_hinge",
             "description": "Swing from the 9 o'clock L position to the 3 o'clock L position. Focuses on wrist hinge and unhinge without full swing complexity.",
             "duration_min": 8},
        ]

        if last_analysis and last_analysis.get("coaching"):
            focus_areas = {c.get("area", "") for c in last_analysis["coaching"] if c.get("severity") in ("high", "medium")}
            priority = [d for d in all_drills if d["focus"] in focus_areas]
            rest     = [d for d in all_drills if d["focus"] not in focus_areas]
            return (priority + rest)[:5]

        return all_drills[:5]

    # ── private helpers ───────────────────────────────────────────────

    def _phase_single(self, lms: List[Dict]) -> str:
        lw = _pt(lms, "left_wrist")
        ls = _pt(lms, "left_shoulder")
        if lw and ls:
            if lw["y"] < ls["y"] - 0.05:   # wrist clearly above shoulder
                return "backswing / follow-through"
            if lw["y"] < ls["y"]:
                return "mid-swing"
        return "address / impact"

    def _estimate_tempo(self, frames: List[Dict]) -> float:
        heights = []
        for f in frames:
            lms = f.get("landmarks", [])
            lw  = _pt(lms, "left_wrist") if lms else None
            heights.append(lw["y"] if lw else None)
        clean = [h for h in heights if h is not None]
        if len(clean) < 6:
            return 3.0
        peak_idx = clean.index(min(clean))
        if peak_idx == 0 or peak_idx >= len(clean) - 1:
            return 3.0
        back   = peak_idx
        down   = len(clean) - peak_idx
        return round(back / max(down, 1), 2)

    def _aggregate_bio(self, bio_list: List[Dict]) -> Dict[str, Any]:
        if not bio_list:
            return {}
        agg: Dict[str, Any] = {}
        keys = {k for b in bio_list for k in b}
        for k in keys:
            vals = [b[k] for b in bio_list if k in b and isinstance(b[k], (int, float))]
            if vals:
                agg[f"{k}_avg"] = round(sum(vals) / len(vals), 1)
                agg[f"{k}_max"] = round(max(vals), 1)
                agg[f"{k}_min"] = round(min(vals), 1)
        return agg

    def _rule_tips(self, bio: Dict[str, Any]) -> List[str]:
        tips: List[str] = []
        sa = bio.get("spine_angle")
        if sa is not None:
            if sa < 25:
                tips.append(f"Spine too upright ({sa}°) — bend more from the hips at address.")
            elif sa > 50:
                tips.append(f"Spine too steep ({sa}°) — reduce forward lean for freer rotation.")
            else:
                tips.append(f"Good spine angle: {sa}°.")
        lkf = bio.get("lead_knee_flex")
        if lkf is not None:
            if lkf > 175:
                tips.append("Add flex to your lead knee — avoid locking it at address.")
            elif lkf < 130:
                tips.append("Lead knee over-flexed — slight reduction improves stability.")
        laa = bio.get("lead_arm_angle")
        if laa is not None:
            if laa < 150:
                tips.append(f"Lead arm bends too much ({laa}°) — focus on extension through the backswing.")
            else:
                tips.append("Good lead arm extension.")
        xf = bio.get("x_factor")
        if xf is not None and xf < 5:
            tips.append("Low hip-shoulder separation — turn shoulders more while resisting with hips.")
        return tips[:3]

    def _swing_coaching(self, agg: Dict, tempo: float) -> List[Dict]:
        coaching: List[Dict] = []
        # Tempo
        if tempo < 2.0:
            coaching.append({"area": "tempo", "severity": "high",
                             "tip": f"Swing too fast (ratio {tempo:.1f}:1) — slow your backswing for better control. Tour average is ~3:1."})
        elif 2.5 <= tempo <= 3.5:
            coaching.append({"area": "tempo", "severity": "ok",
                             "tip": f"Great tempo: {tempo:.1f}:1 — consistent with tour averages."})
        else:
            coaching.append({"area": "tempo", "severity": "medium",
                             "tip": f"Tempo {tempo:.1f}:1 — aim for 3:1 backswing-to-downswing ratio."})
        # Spine
        sa = agg.get("spine_angle_avg")
        if sa is not None:
            if sa < 25:
                coaching.append({"area": "setup", "severity": "medium",
                                 "tip": f"Avg spine angle {sa}° too upright — more hip hinge at address."})
            elif sa > 50:
                coaching.append({"area": "setup", "severity": "medium",
                                 "tip": f"Avg spine angle {sa}° too steep — stand a little taller."})
        # Lead arm
        laa = agg.get("lead_arm_angle_min")
        if laa is not None and laa < 150:
            coaching.append({"area": "backswing", "severity": "medium",
                             "tip": f"Lead arm minimum angle {laa}° — keep it straighter through the swing."})
        # X-factor
        xf = agg.get("x_factor_max")
        if xf is not None and xf < 8:
            coaching.append({"area": "rotation", "severity": "low",
                             "tip": "Low X-factor — rotate shoulders more while keeping hips quieter to generate power."})
        return coaching[:4]

    def _swing_score(self, agg: Dict, tempo: float) -> int:
        score = 55  # base
        # Tempo ±15
        if 2.5 <= tempo <= 3.5:
            score += 15
        elif 2.0 <= tempo < 2.5 or 3.5 < tempo <= 4.5:
            score += 8
        # Spine ±10
        sa = agg.get("spine_angle_avg")
        if sa and 30 <= sa <= 45:
            score += 10
        elif sa and (25 <= sa < 30 or 45 < sa <= 50):
            score += 5
        # Lead arm ±10
        laa = agg.get("lead_arm_angle_min")
        if laa and laa >= 165:
            score += 10
        elif laa and laa >= 150:
            score += 5
        # X-factor ±5
        xf = agg.get("x_factor_max")
        if xf and xf >= 15:
            score += 5
        elif xf and xf >= 8:
            score += 3
        # Frame coverage bonus ±5
        if agg:
            score += 5
        return min(100, max(0, score))

    # ── storage ──────────────────────────────────────────────────────

    def _read(self) -> Dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"swings": []}

    def _write(self, data: Dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _gen_id() -> str:
        ts = datetime.utcnow().isoformat()
        return hashlib.sha256(ts.encode()).hexdigest()[:12]
