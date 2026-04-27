"""Golf Swing Elite v9 — Production Analysis Layer

Wraps GolfVisionEngine and adds:
- 7-phase detection
- Named error taxonomy (over the top, casting, early extension, etc.)
- Score breakdown by category
- QA validation (no hallucinated metrics)
- PGA player comparisons
- Adaptive level detection
- Language-aware coaching (ES / EN)
- Progress tracking vs history
- Live coach commands
- Drill prescriptions with body sensation cues
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── PGA reference values ────────────────────────────────────────────────────
_PRO_REFS = {
    "rory":      {"spine_angle": 38, "hip_turn": 45, "shoulder_turn": 110, "x_factor": 45, "tempo": 3.1},
    "tiger":     {"spine_angle": 35, "hip_turn": 40, "shoulder_turn": 108, "x_factor": 52, "tempo": 2.9},
    "scheffler": {"spine_angle": 37, "hip_turn": 42, "shoulder_turn": 106, "x_factor": 46, "tempo": 3.2},
}

# ── Error definitions: name, detection fn, ES/EN messages ──────────────────
_ERRORS_ES = {
    "over_the_top": {
        "name":       "Por encima del plano (Over the Top)",
        "cause":      "El brazo dominante empuja el palo hacia afuera en la bajada, cruzando la línea de vuelo",
        "effect":     "Produce tiros con slice o pull. Pérdida de distancia hasta 15%",
        "correction": "Inicia la bajada dejando caer el codo derecho hacia la cadera derecha antes de girar",
        "drill":      "Drill del barril: imagina un barril bajo tu codo derecho — bájalo sin tocarlo",
        "sensation":  "Siente como si 'metieras' el palo bajo el arco en la bajada",
        "home_drill": "Practica bajadas lentas frente al espejo chequeando la posición del codo a las 9h",
        "pga_ref":    "Tiger Woods — maestro del plano interno en la transición",
    },
    "early_extension": {
        "name":       "Extensión prematura (Early Extension)",
        "cause":      "Las caderas se acercan a la pelota durante la bajada, interrumpiendo la rotación",
        "effect":     "Inconsistencia severa — shots fat, thin o tope de palo",
        "correction": "Mantén el ángulo de la cadera al doblar desde las caderas durante toda la bajada",
        "drill":      "Drill de la silla: pon una silla detrás de ti. Mantén el contacto de glúteos con el respaldo hasta el impacto",
        "sensation":  "Siente que tu cadera se aleja de la pelota mientras gira",
        "home_drill": "Swing en slow motion frente a espejo lateral — no dejes que la cadera avance hacia la pelota",
        "pga_ref":    "Scottie Scheffler — mantiene perfecta profundidad de cadera en la bajada",
    },
    "casting": {
        "name":       "Lanzamiento prematuro (Casting / Early Release)",
        "cause":      "Las muñecas se liberan demasiado pronto — antes del impacto",
        "effect":     "Pérdida de potencia, shots débiles y altos, impact con ángulo negativo",
        "correction": "Mantén el ángulo de las muñecas ('lag') hasta que el brazo izquierdo llegue a las 8h",
        "drill":      "Drill de la bolsa de impacto: golpea la bolsa en slow motion manteniendo la flexión de muñeca",
        "sensation":  "Siente como si el palo 'colgara' detrás de ti en la bajada",
        "home_drill": "Agarra el palo y practica la bajada hasta el impacto sin soltar el ángulo. 20 reps/día",
        "pga_ref":    "Rory McIlroy — lag excepcional que genera alta velocidad con poco esfuerzo aparente",
    },
    "reverse_pivot": {
        "name":       "Pivote reverso (Reverse Pivot)",
        "cause":      "El peso se transfiere hacia adelante en el backswing y hacia atrás en el downswing — lo opuesto al ideal",
        "effect":     "Pérdida masiva de potencia y falta de control de dirección",
        "correction": "Siente que tu peso carga en el talón del pie trasero en el backswing",
        "drill":      "Drill del pie: levanta los dedos del pie delantero en el backswing para forzar el peso al pie trasero",
        "sensation":  "Siente presión en el talón derecho al llegar al top del swing",
        "home_drill": "Practica turnos lentos con conciencia del peso. Grábate de frente para verificar",
        "pga_ref":    "Tiger Woods — transferencia de peso perfecta, como plantar el talón derecho en el backswing",
    },
    "poor_weight_shift": {
        "name":       "Transferencia de peso deficiente",
        "cause":      "El peso no se traslada completamente al pie delantero en el downswing e impacto",
        "effect":     "Impacto débil, shots altos y cortos, falta de compresión del ball",
        "correction": "Inicia el downswing con un pequeño lateral bump de la cadera hacia el objetivo",
        "drill":      "Drill del paso: practica swings dando un pequeño paso con el pie izquierdo al iniciar la bajada",
        "sensation":  "Siente el peso llegando al borde exterior del pie izquierdo en el impacto",
        "home_drill": "Swings lentos en casa — levanta el talón derecho en el follow-through para verificar la transferencia",
        "pga_ref":    "Rory McIlroy — transferencia lateral explosiva que genera su potencia característica",
    },
    "loss_of_posture": {
        "name":       "Pérdida de postura",
        "cause":      "El ángulo de la columna cambia durante el swing — levantamiento o agachamiento no intencional",
        "effect":     "Inconsistencia directa: fat shots, thins, tops, y variación de distancia alta",
        "correction": "Mantén el ángulo de inclinación desde las caderas durante todo el swing. Imagina una barra en tu espalda",
        "drill":      "Drill de la pared: haz swings lentamente con la espalda contra la pared. No despegues del contacto",
        "sensation":  "Siente la cabeza y la espalda moviéndose en un arco circular, no arriba/abajo",
        "home_drill": "Haz swings frente a espejo. Dibuja una línea horizontal a la altura de tu cabeza y mantenla constante",
        "pga_ref":    "Scottie Scheffler — notable estabilidad de postura en toda la secuencia",
    },
}

_ERRORS_EN = {
    "over_the_top": {
        "name":       "Over the Top",
        "cause":      "The dominant arm pushes the club outward on the downswing, crossing the target line",
        "effect":     "Produces slices or pulls. Distance loss up to 15%",
        "correction": "Start the downswing by dropping the right elbow toward the right hip before rotating",
        "drill":      "Barrel Drill: imagine a barrel under your right elbow — lower it without touching it",
        "sensation":  "Feel like you're 'tucking' the club under the arc on the way down",
        "home_drill": "Slow-motion downswings in front of a mirror, checking elbow position at 9 o'clock",
        "pga_ref":    "Tiger Woods — master of the inside path on the transition",
    },
    "early_extension": {
        "name":       "Early Extension",
        "cause":      "Hips thrust toward the ball during the downswing, blocking rotation",
        "effect":     "Severe inconsistency — fat, thin, and hosel shots",
        "correction": "Maintain hip depth by hinging from the hips throughout the entire downswing",
        "drill":      "Chair Drill: place a chair behind you. Keep glute contact with the back rest through impact",
        "sensation":  "Feel your hip moving away from the ball as it rotates",
        "home_drill": "Slow-motion swing in a side mirror — hips must not thrust toward the ball",
        "pga_ref":    "Scottie Scheffler — maintains perfect hip depth throughout the downswing",
    },
    "casting": {
        "name":       "Casting / Early Release",
        "cause":      "Wrists release too early — before impact",
        "effect":     "Power loss, weak high shots, negative angle of attack at impact",
        "correction": "Maintain the wrist angle ('lag') until the lead arm reaches the 8 o'clock position",
        "drill":      "Impact Bag Drill: hit the bag slowly while keeping wrist hinge through the strike",
        "sensation":  "Feel the club 'hanging' behind you on the downswing",
        "home_drill": "Grab the club and rehearse the downswing without releasing the angle. 20 reps/day",
        "pga_ref":    "Rory McIlroy — exceptional lag that generates high speed with seemingly little effort",
    },
    "reverse_pivot": {
        "name":       "Reverse Pivot",
        "cause":      "Weight shifts forward on backswing and back on downswing — opposite of ideal",
        "effect":     "Massive power loss and directional inconsistency",
        "correction": "Feel your weight loading into the back heel on the backswing",
        "drill":      "Toes Drill: lift front toes on the backswing to force weight into the back foot",
        "sensation":  "Feel pressure in your back heel as you reach the top of the swing",
        "home_drill": "Slow-motion turns with weight awareness. Record from the front to verify",
        "pga_ref":    "Tiger Woods — perfect weight transfer, feeling the back heel planted on the backswing",
    },
    "poor_weight_shift": {
        "name":       "Poor Weight Transfer",
        "cause":      "Weight doesn't fully transfer to the front foot at impact",
        "effect":     "Weak impact, high weak shots, lack of ball compression",
        "correction": "Initiate the downswing with a small lateral hip bump toward the target",
        "drill":      "Step Drill: step forward with the front foot as you begin the downswing",
        "sensation":  "Feel the weight reaching the outer edge of your front foot at impact",
        "home_drill": "Slow swings at home — lift the back heel in the follow-through to verify transfer",
        "pga_ref":    "Rory McIlroy — explosive lateral transfer that generates his characteristic power",
    },
    "loss_of_posture": {
        "name":       "Loss of Posture",
        "cause":      "Spine angle changes during the swing — unintentional rising or dipping",
        "effect":     "Direct inconsistency: fat shots, thins, tops, and high distance variation",
        "correction": "Maintain your hip-hinge tilt throughout the swing. Imagine a rod along your back",
        "drill":      "Wall Drill: make slow swings with your back against a wall. Don't lose contact",
        "sensation":  "Feel your head and back moving in a circular arc, not up/down",
        "home_drill": "Swing in a mirror. Draw a horizontal line at head height and keep it constant",
        "pga_ref":    "Scottie Scheffler — notably stable posture across the full sequence",
    },
}

# ── Live coach commands (short, camera-ready) ───────────────────────────────
_LIVE_CUES_ES = {
    "over_the_top":       "Mete el codo",
    "early_extension":    "Profundidad de cadera",
    "casting":            "Mantén el lag",
    "reverse_pivot":      "Peso al talón",
    "poor_weight_shift":  "Bombea la cadera",
    "loss_of_posture":    "Mantén postura",
    "tempo_fast":         "Más lento",
    "tempo_ok":           "Bien",
    "spine_ok":           "Buena postura ✓",
    "no_data":            "Otra vez",
}
_LIVE_CUES_EN = {
    "over_the_top":       "Tuck the elbow",
    "early_extension":    "Hip depth",
    "casting":            "Hold the lag",
    "reverse_pivot":      "Load the back heel",
    "poor_weight_shift":  "Bump the hip",
    "loss_of_posture":    "Hold posture",
    "tempo_fast":         "Slower",
    "tempo_ok":           "Good",
    "spine_ok":           "Good posture ✓",
    "no_data":            "Again",
}

# ── Motivational openers ─────────────────────────────────────────────────────
_STRENGTH_ES = [
    "Buen contacto", "Postura estable", "Buen tempo", "Extensión sólida",
    "Buena rotación", "Equilibrio sólido",
]
_STRENGTH_EN = [
    "Good contact", "Stable posture", "Good tempo", "Solid extension",
    "Good rotation", "Solid balance",
]


class GolfSwingElite:
    """
    Elite analysis wrapper. Instantiated per user via the endpoint.
    Requires a GolfVisionEngine instance (existing engine).
    """

    def __init__(self, vision_engine: Any) -> None:
        self._ve = vision_engine

    # ── Public API ──────────────────────────────────────────────────────────

    def analyze(
        self,
        frames:  List[Dict],
        club:    str   = "unknown",
        fps:     float = 30.0,
        lang:    str   = "es",
    ) -> Dict[str, Any]:
        """Full elite swing analysis. Returns structured JSON ready for UI."""
        lang = "en" if lang.lower().startswith("en") else "es"

        # 1 — Base analysis from existing engine
        base = self._ve.analyze_swing_sequence(frames, club, fps)

        # 2 — QA: validate we have enough data
        qa = self._qa_validate(base, frames)

        # 3 — Phase detection
        phases = self._detect_phases(frames)

        # 4 — Error detection
        raw_errors = self._detect_errors(base)
        errors     = self._format_errors(raw_errors[:3], lang)

        # 5 — Score breakdown
        breakdown = self._score_breakdown(base, raw_errors)

        # 6 — Level detection
        level = self._detect_level(base.get("score", 55), base.get("biomechanics", {}))

        # 7 — Pro comparisons
        comparisons = self._pro_comparisons(base, lang)

        # 8 — Strengths
        strengths = self._detect_strengths(base, raw_errors, lang)

        # 9 — History progress
        progress = self._compare_history(base.get("score", 0))

        # 10 — Next step
        next_step = self._next_step(raw_errors, lang)

        # 11 — Sequencing note
        sequencing = self._sequencing(base, lang)

        return {
            "status":       "ok",
            "lang":         lang,
            "score":        base.get("score", 0),
            "score_breakdown": breakdown,
            "potential":    min(100, base.get("score", 0) + max(0, len(raw_errors) * 7)),
            "tempo_ratio":  base.get("tempo_ratio", 0.0),
            "frame_count":  len(frames),
            "duration_s":   base.get("duration_s", 0),
            "club":         club,
            "level":        level,
            "phases":       phases,
            "strengths":    strengths,
            "errors":       errors,
            "pro_comparisons": comparisons,
            "sequencing":   sequencing,
            "next_step":    next_step,
            "progress":     progress,
            "qa":           qa,
            "biomechanics": base.get("biomechanics", {}),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def live_cue(self, landmarks: List[Dict], lang: str = "es") -> Dict[str, str]:
        """Single-frame live coaching cue for camera overlay."""
        lang = "en" if lang.lower().startswith("en") else "es"
        cues = _LIVE_CUES_EN if lang == "en" else _LIVE_CUES_ES

        if not landmarks:
            return {"cue": cues["no_data"], "color": "#888"}

        try:
            bio   = self._ve.compute_biomechanics(landmarks)
            phase = self._ve._phase_single(landmarks)
            errors = self._detect_errors({"biomechanics": bio, "tempo_ratio": 3.0})
            if errors:
                cue = cues.get(errors[0], cues["no_data"])
                return {"cue": cue, "color": "#ff6b6b", "phase": phase}
            sa = bio.get("spine_angle")
            if sa and 30 <= sa <= 45:
                return {"cue": cues["spine_ok"], "color": "#00e676", "phase": phase}
        except Exception:
            pass

        return {"cue": cues["no_data"], "color": "#aaa"}

    def progress_report(self, history_items: List[Dict], lang: str = "es") -> Dict[str, Any]:
        """Builds trend analysis from stored swing history."""
        if not history_items:
            return {"available": False}
        scores = [h.get("score", 0) for h in history_items if h.get("score")]
        if len(scores) < 2:
            return {"available": False, "score": scores[0] if scores else 0}
        trend   = scores[-1] - scores[0]
        avg     = round(sum(scores) / len(scores), 1)
        best    = max(scores)
        recent3 = scores[-3:] if len(scores) >= 3 else scores
        improving = recent3[-1] > recent3[0] if len(recent3) >= 2 else False
        msg_es = f"Mejoraste +{trend:.0f} puntos" if trend > 0 else (f"Bajaste {abs(trend):.0f} puntos" if trend < 0 else "Sin cambio")
        msg_en = f"Improved +{trend:.0f} points" if trend > 0 else (f"Down {abs(trend):.0f} points" if trend < 0 else "No change")
        return {
            "available":  True,
            "scores":     scores[-10:],
            "trend":      round(trend, 1),
            "avg":        avg,
            "best":       best,
            "improving":  improving,
            "message":    msg_en if lang == "en" else msg_es,
        }

    # ── Private helpers ─────────────────────────────────────────────────────

    def _qa_validate(self, base: Dict, frames: List[Dict]) -> Dict:
        issues = []
        if len(frames) < 5:
            issues.append("Muy pocos fotogramas — el análisis puede ser impreciso" if True else
                          "Too few frames — analysis may be imprecise")
        bio = base.get("biomechanics", {})
        if not bio:
            issues.append("Sin datos biomecánicos — verificar pose detection")
        if base.get("tempo_ratio", 0) <= 0:
            issues.append("Tempo no calculado")
        confidence = "high" if len(frames) >= 20 and bio else ("medium" if len(frames) >= 8 else "low")
        return {
            "confidence": confidence,
            "frame_count": len(frames),
            "issues": issues,
            "valid": len(issues) == 0 or (len(issues) == 1 and "tempo" in issues[0].lower()),
        }

    def _detect_phases(self, frames: List[Dict]) -> List[str]:
        """Map frames to swing phases using wrist height heuristic."""
        if not frames:
            return []
        heights = []
        for f in frames:
            lms = f.get("landmarks", [])
            if len(lms) > 16:
                lw = lms[15]  # left wrist
                ls = lms[11]  # left shoulder
                if lw.get("visibility", 1) > 0.2:
                    heights.append(lw.get("y", 0.5) - ls.get("y", 0.5))
                else:
                    heights.append(None)
            else:
                heights.append(None)

        clean = [(i, h) for i, h in enumerate(heights) if h is not None]
        if not clean:
            return ["unknown"] * len(frames)

        _, min_h = min(clean, key=lambda x: x[1])  # highest point (lowest y)
        peak_idx = [i for i, h in clean if h == min_h][0]
        total    = len(frames)

        phases = []
        for i in range(total):
            pct = i / max(total - 1, 1)
            if pct < 0.08:
                phases.append("setup")
            elif pct < 0.20:
                phases.append("takeaway")
            elif i < peak_idx * 0.85:
                phases.append("backswing")
            elif abs(i - peak_idx) <= max(1, total * 0.06):
                phases.append("top")
            elif i < peak_idx + (total - peak_idx) * 0.25:
                phases.append("transition")
            elif i < peak_idx + (total - peak_idx) * 0.55:
                phases.append("downswing")
            elif i < peak_idx + (total - peak_idx) * 0.75:
                phases.append("impact")
            else:
                phases.append("finish")
        return phases

    def _detect_errors(self, base: Dict) -> List[str]:
        """Returns list of error keys ordered by severity."""
        bio   = base.get("biomechanics", {})
        tempo = base.get("tempo_ratio", 3.0)
        found: List[Tuple[str, float]] = []  # (error_key, severity_score)

        # Lead arm angle — casting proxy
        laa_min = bio.get("lead_arm_angle_min")
        if laa_min is not None and laa_min < 140:
            found.append(("casting", 3 - laa_min / 70))

        # Spine angle variance — loss of posture
        sa_max = bio.get("spine_angle_max")
        sa_min = bio.get("spine_angle_min")
        if sa_max and sa_min and (sa_max - sa_min) > 18:
            found.append(("loss_of_posture", (sa_max - sa_min) / 10))

        # Hip vs shoulder turn — over the top proxy
        ht_max = bio.get("hip_turn_max")
        st_max = bio.get("shoulder_turn_max")
        if ht_max and st_max and ht_max > 0:
            ratio = st_max / ht_max if ht_max > 0 else 1
            if ratio < 1.2:  # shoulders barely outpace hips → over the top risk
                found.append(("over_the_top", (1.5 - ratio) * 2))

        # Lead wrist height — early extension proxy
        wh_min = bio.get("lead_wrist_height_min")
        if wh_min is not None and wh_min < -0.05:
            found.append(("early_extension", abs(wh_min) * 5))

        # X-factor / reverse pivot proxy
        xf_max = bio.get("x_factor_max")
        if xf_max is not None and xf_max < 4:
            found.append(("reverse_pivot", (5 - xf_max)))

        # Weight shift: check hip_turn progression (proxy)
        ht_avg = bio.get("hip_turn_avg")
        if ht_avg is not None and ht_avg < 8:
            found.append(("poor_weight_shift", (10 - ht_avg) / 2))

        # Sort by severity descending
        found.sort(key=lambda x: x[1], reverse=True)
        return [k for k, _ in found]

    def _format_errors(self, error_keys: List[str], lang: str) -> List[Dict]:
        db = _ERRORS_EN if lang == "en" else _ERRORS_ES
        result = []
        for key in error_keys:
            if key in db:
                result.append({"key": key, **db[key]})
        return result

    def _score_breakdown(self, base: Dict, errors: List[str]) -> Dict[str, int]:
        bio   = base.get("biomechanics", {})
        tempo = base.get("tempo_ratio", 3.0)
        total = base.get("score", 55)

        setup = 20
        sa = bio.get("spine_angle_avg")
        if sa:
            if 30 <= sa <= 45:   setup = 18
            elif 25 <= sa < 30 or 45 < sa <= 52: setup = 12
            else:                setup = 7
        if "loss_of_posture" in errors: setup = max(5, setup - 6)

        backswing = 18
        laa = bio.get("lead_arm_angle_min")
        if laa:
            if laa >= 165:  backswing = 18
            elif laa >= 150: backswing = 13
            else:            backswing = 7
        if "over_the_top" in errors: backswing = max(5, backswing - 5)
        if "casting" in errors:      backswing = max(4, backswing - 5)

        transition = 20
        xf = bio.get("x_factor_max")
        if xf:
            if xf >= 15: transition = 20
            elif xf >= 8: transition = 14
            else:          transition = 8
        if "reverse_pivot" in errors:   transition = max(4, transition - 6)
        if "early_extension" in errors: transition = max(5, transition - 5)

        impact = 22
        if "casting" in errors:       impact = max(5, impact - 8)
        if "early_extension" in errors: impact = max(5, impact - 7)
        if "poor_weight_shift" in errors: impact = max(5, impact - 6)

        balance = 20
        if 2.5 <= tempo <= 3.5: balance = 20
        elif 2.0 <= tempo < 2.5 or 3.5 < tempo <= 4.0: balance = 13
        else: balance = 7
        if "loss_of_posture" in errors: balance = max(4, balance - 5)

        return {
            "setup":      setup,
            "backswing":  backswing,
            "transition": transition,
            "impact":     impact,
            "balance":    balance,
        }

    def _detect_level(self, score: int, bio: Dict) -> str:
        if score >= 78: return "advanced"
        if score >= 62: return "intermediate"
        return "beginner"

    def _pro_comparisons(self, base: Dict, lang: str) -> List[Dict]:
        bio = base.get("biomechanics", {})
        result = []
        sa  = bio.get("spine_angle_avg")
        xf  = bio.get("x_factor_max")
        tmp = base.get("tempo_ratio", 0.0)

        for pro, refs in _PRO_REFS.items():
            diffs = []
            if sa:
                d = sa - refs["spine_angle"]
                label_es = f"Ángulo de columna: {'+' if d>0 else ''}{d:.0f}° vs {pro.capitalize()}"
                label_en = f"Spine angle: {'+' if d>0 else ''}{d:.0f}° vs {pro.capitalize()}"
                diffs.append(label_en if lang == "en" else label_es)
            if xf:
                d = xf - refs["x_factor"]
                label_es = f"X-factor: {'+' if d>0 else ''}{d:.0f}° vs {pro.capitalize()}"
                label_en = f"X-factor: {'+' if d>0 else ''}{d:.0f}° vs {pro.capitalize()}"
                diffs.append(label_en if lang == "en" else label_es)
            if tmp and tmp > 0:
                d = round(tmp - refs["tempo"], 1)
                label_es = f"Tempo: {'+' if d>0 else ''}{d} ratio vs {pro.capitalize()}"
                label_en = f"Tempo: {'+' if d>0 else ''}{d} ratio vs {pro.capitalize()}"
                diffs.append(label_en if lang == "en" else label_es)
            if diffs:
                result.append({"pro": pro.capitalize(), "diffs": diffs[:2]})
        return result[:2]

    def _detect_strengths(self, base: Dict, errors: List[str], lang: str) -> List[str]:
        bio   = base.get("biomechanics", {})
        tempo = base.get("tempo_ratio", 0.0)
        out   = []
        sa = bio.get("spine_angle_avg")
        if sa and 30 <= sa <= 45 and "loss_of_posture" not in errors:
            out.append(f"Ángulo de columna sólido ({sa:.0f}°)" if lang == "es" else f"Solid spine angle ({sa:.0f}°)")
        laa = bio.get("lead_arm_angle_min")
        if laa and laa >= 160 and "casting" not in errors:
            out.append("Brazo líder extendido correctamente" if lang == "es" else "Good lead arm extension")
        xf = bio.get("x_factor_max")
        if xf and xf >= 12:
            out.append(f"Buena separación cadera-hombro ({xf:.0f}°)" if lang == "es" else f"Good hip-shoulder separation ({xf:.0f}°)")
        if 2.5 <= tempo <= 3.5:
            out.append(f"Excelente tempo: {tempo:.1f}:1" if lang == "es" else f"Excellent tempo: {tempo:.1f}:1")
        if not out:
            out = ["Postura básica correcta" if lang == "es" else "Basic posture is correct"]
        return out[:3]

    def _sequencing(self, base: Dict, lang: str) -> str:
        bio = base.get("biomechanics", {})
        xf  = bio.get("x_factor_max", 0) or 0
        ht  = bio.get("hip_turn_max", 0) or 0
        st  = bio.get("shoulder_turn_max", 0) or 0
        if xf < 5:
            return ("Los hombros y caderas se mueven a la vez — la cadera debe liderar la bajada"
                    if lang == "es" else
                    "Shoulders and hips moving together — hips should lead the downswing")
        if st > 0 and ht > 0 and (ht / st) < 0.35:
            return ("Excelente separación: cadera → torso → brazos → palo"
                    if lang == "es" else
                    "Excellent separation: hips → torso → arms → club")
        return ("Secuencia aceptable — mejorar la iniciación de caderas"
                if lang == "es" else
                "Acceptable sequence — improve hip initiation")

    def _compare_history(self, current_score: int) -> Dict[str, Any]:
        try:
            hist = self._ve.get_history(limit=5)
            items = hist.get("items", [])
            if len(items) < 2:
                return {"available": False}
            prev_scores = [i.get("score", 0) for i in items[1:]]
            avg_prev = sum(prev_scores) / len(prev_scores) if prev_scores else current_score
            delta    = round(current_score - avg_prev, 1)
            return {
                "available":  True,
                "delta":      delta,
                "prev_avg":   round(avg_prev, 1),
                "sessions":   len(prev_scores),
            }
        except Exception:
            return {"available": False}

    def _next_step(self, error_keys: List[str], lang: str) -> str:
        db = _ERRORS_EN if lang == "en" else _ERRORS_ES
        if not error_keys:
            return ("Mantén la consistencia — graba otro swing y busca la repetición" if lang == "es"
                    else "Stay consistent — record another swing and look for repeatability")
        top = db.get(error_keys[0], {})
        drill = top.get("drill", "")
        correction = top.get("correction", "")
        if lang == "es":
            return f"Enfócate en: {top.get('name', '')} — {correction}"
        return f"Focus on: {top.get('name', '')} — {correction}"
