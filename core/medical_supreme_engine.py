from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.agent_schema import build_response, degraded


class MedicalSupremeEngine:
    """
    Elite preventive and clinical intelligence engine.
    Urgency classification, multi-horizon recommendations, risk stratification.
    NOT a substitute for licensed medical care.
    """

    DISCLAIMER = (
        "This is not medical advice. Always consult a licensed physician "
        "before acting on any health-related information."
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, query: str) -> Dict[str, Any]:
        if not (query or "").strip():
            return degraded("No symptoms or health query provided", confidence=0.2)
        try:
            return self._analyze_impl(query)
        except Exception as exc:
            return degraded(f"Medical analysis failed: {exc}", confidence=0.25)

    def _analyze_impl(self, query: str) -> Dict[str, Any]:
        text   = (query or "").lower()
        triage = self._full_triage(text)

        urgency    = triage["urgency"]
        risk_raw   = triage["risk_level"]
        # Normalize to schema-valid values
        risk_level = "high" if risk_raw in ("critical", "high", "urgent") else ("low" if risk_raw == "low" else "medium")
        confidence = float(triage.get("confidence", 0.75))

        rec_list   = triage.get("recommendation", [])
        top_action = rec_list[0] if isinstance(rec_list, list) and rec_list else str(rec_list or "Consult a physician")

        short_term = triage.get("short_term", [])
        red_flags  = triage.get("red_flags", [])

        signals = [f"Urgency: {urgency}", f"Domain: {triage['domain']}"]
        if red_flags:
            signals.append(f"Red flag: {red_flags[0]}")

        return build_response(
            confidence=confidence,
            insight=(
                f"Clinical domain: {triage['domain']}. "
                f"Urgency: {urgency}. "
                f"{triage['summary']}. "
                f"{self.DISCLAIMER}"
            ),
            risk_level=risk_level,
            action=top_action,
            reason=(
                f"Triage reasoning: {triage['reasoning'][:150]}. "
                f"Top risk signal: {red_flags[0] if red_flags else 'none identified'}."
            ),
            signals_used=signals + short_term[:2],
            data_sources=["clinical_triage_engine_internal", "symptom_pattern_library"],
            reasoning_path=[
                f"1. Parse query for symptom keywords",
                f"2. Match to clinical domain: {triage['domain']}",
                f"3. Urgency classification: {urgency}",
                f"4. Risk stratification: {risk_level}",
                f"5. Primary action: {top_action[:80]}",
            ],
            data_freshness=1.0,
            data_completeness=0.80 if triage["domain"] != "general_medicine" else 0.45,
        )

    def symptom_triage(self, symptoms: str) -> Dict[str, Any]:
        return self.analyze(symptoms)

    # ------------------------------------------------------------------
    # Full triage
    # ------------------------------------------------------------------

    def _full_triage(self, t: str) -> Dict[str, Any]:
        if self._is_emergency(t):
            return self._emergency_response()
        if self._is_cardiac(t):
            return self._cardiac_response()
        if self._is_fever(t):
            return self._fever_response()
        if self._is_neurological(t):
            return self._neurological_response()
        if self._is_musculoskeletal(t):
            return self._musculoskeletal_response()
        if self._is_fatigue(t):
            return self._fatigue_response()
        if self._is_gastrointestinal(t):
            return self._gi_response()
        if self._is_mental_health(t):
            return self._mental_health_response()
        if self._is_longevity(t):
            return self._longevity_response()
        return self._general_response()

    # ------------------------------------------------------------------
    # Pattern detectors
    # ------------------------------------------------------------------

    def _is_emergency(self, t: str) -> bool:
        return any(w in t for w in [
            "emergency", "emergencia", "no puedo respirar", "can't breathe",
            "desmayo", "faint", "unconscious", "sangrado intenso", "heavy bleeding",
            "stroke", "derrame", "convulsión", "seizure",
        ])

    def _is_cardiac(self, t: str) -> bool:
        return (
            "palpitaciones" in t
            or "chest pain" in t
            or "dolor de pecho" in t
            or ("pecho" in t and "dolor" in t)
            or ("chest" in t and any(w in t for w in ["pain", "tight", "pressure", "heavy"]))
            or any(w in t for w in ["corazón", "heart", "arritmia", "arrhythmia", "taquicardia"])
        )

    def _is_fever(self, t: str) -> bool:
        return any(w in t for w in [
            "fever", "fiebre", "temperatura alta", "caliente", "chills", "escalofríos",
        ])

    def _is_neurological(self, t: str) -> bool:
        return any(w in t for w in [
            "headache", "dolor cabeza", "migraña", "migraine",
            "dizziness", "mareo", "vertigo", "vértigo",
            "numbness", "entumecimiento", "vision", "visión",
            "confusion", "confusión", "memory", "memoria",
        ])

    def _is_musculoskeletal(self, t: str) -> bool:
        return any(w in t for w in [
            "muscle", "músculo", "joint", "articulación",
            "espalda", "back", "rodilla", "knee", "hombro", "shoulder",
            "cuello", "neck", "lumbar", "tendón", "tendon",
        ]) or (any(w in t for w in ["dolor", "pain"]) and not self._is_cardiac(t))

    def _is_fatigue(self, t: str) -> bool:
        return any(w in t for w in [
            "fatiga", "fatigue", "cansancio", "tired", "exhausted",
            "no tengo energía", "low energy", "sleep", "sueño", "insomnia",
        ])

    def _is_gastrointestinal(self, t: str) -> bool:
        return any(w in t for w in [
            "stomach", "estómago", "digestion", "digestión", "nausea", "náusea",
            "vomit", "vómito", "diarrhea", "diarrea", "bloating", "hinchazón",
            "acid", "acidez", "reflux", "reflujo",
        ])

    def _is_mental_health(self, t: str) -> bool:
        return any(w in t for w in [
            "anxiety", "ansiedad", "stress", "estrés", "depression", "depresión",
            "mood", "ánimo", "panic", "pánico", "overwhelmed", "burnout", "mental",
        ])

    def _is_longevity(self, t: str) -> bool:
        return any(w in t for w in [
            "longevity", "longevidad", "aging", "envejecimiento", "biohack",
            "optimize", "optimizar", "healthspan", "lifespan", "biomarker",
            "supplement", "suplemento", "rendimiento",
        ])

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------

    def _emergency_response(self) -> Dict:
        return {
            "urgency": "emergency",
            "domain":  "emergency_medicine",
            "summary": "EMERGENCY — Seek immediate medical care now",
            "reasoning": (
                "Symptoms indicate a potentially life-threatening situation requiring "
                "immediate professional evaluation. Do not delay."
            ),
            "recommendation": [
                "CALL EMERGENCY SERVICES NOW — Colombia: 123 / 125",
                "Stay calm, keep the person still, do not give food or water",
                "Do not drive yourself to the hospital if symptomatic",
            ],
            "short_term":   ["Call emergency services immediately"],
            "mid_term":     ["Follow up with specialist within 48h after emergency care"],
            "long_term":    ["Preventive screening to identify and manage root causes"],
            "risk_level":   "critical",
            "red_flags":    ["All emergency symptoms are red flags — never wait"],
            "safe_signals": [],
            "confidence":   0.95,
            "clarity":      "high",
        }

    def _cardiac_response(self) -> Dict:
        return {
            "urgency": "urgent",
            "domain":  "cardiology",
            "summary": "Cardiac / pulmonary signal — urgent evaluation required",
            "reasoning": (
                "Chest pain, pressure, palpitations, or cardiac rhythm irregularities span a wide "
                "clinical spectrum — from musculoskeletal (benign) to acute MI (life-threatening). "
                "Context is critical: onset, duration, radiation, associated sweating or nausea."
            ),
            "recommendation": [
                "Seek urgent medical evaluation same day — ECG is the first test",
                "Note exact onset time, duration, radiation (arm/jaw), diaphoresis, and nausea",
                "If pain is crushing, radiating, or with shortness of breath: call emergency now",
            ],
            "short_term": [
                "ECG within 24h if chest pain or palpitations persist",
                "Measure blood pressure — both arms if possible",
                "Avoid strenuous activity until medically cleared",
            ],
            "mid_term": [
                "Full panel: lipid profile, troponin, hs-CRP, glucose, blood pressure monitoring",
                "Stress test / echocardiogram if risk factors present (age >45, smoker, diabetes, family history)",
                "Cardiology consultation if symptoms recur",
            ],
            "long_term": [
                "Annual cardiovascular risk assessment from age 35",
                "Optimize the modifiable: exercise, sleep, stress, nutrition, HRV monitoring",
                "Coronary calcium score at 40–45 for baseline cardiovascular risk stratification",
            ],
            "risk_level":   "high",
            "red_flags": [
                "Crushing or pressure-type chest pain",
                "Pain radiating to left arm, jaw, or back",
                "Associated diaphoresis, nausea, or shortness of breath",
                "Sudden-onset severe palpitations with near-syncope",
            ],
            "safe_signals": [
                "Pain reproducible with palpation (likely musculoskeletal / costochondritis)",
                "Brief, positional, sharp pain with clear posture cause",
            ],
            "confidence": 0.86,
            "clarity":    "high",
        }

    def _fever_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "infectious_disease",
            "summary": "Fever pattern — infection monitoring and management",
            "reasoning": (
                "Fever is the primary immune response to infection (viral, bacterial, or other). "
                "Duration, magnitude, and associated symptoms determine urgency. "
                "Most fevers in healthy adults are self-limiting viral processes."
            ),
            "recommendation": [
                "Monitor temperature every 4–6 hours — log readings with timestamps",
                "Aggressive hydration: 2.5–3L water/day with electrolytes",
                "Seek physician if: fever >38.5°C, persists >48h, associated with rash, stiff neck, or confusion",
            ],
            "short_term": [
                "Temperature log every 4h — note trend (rising vs. stabilizing)",
                "Paracetamol or ibuprofen per label for comfort if >38°C — do not mask for physician visit",
                "Rest — activity drives temperature up",
            ],
            "mid_term": [
                "CBC, CRP, procalcitonin if fever persists >3 days without clear cause",
                "Rule out atypical infections (dengue, typhoid) if travel history present",
                "Blood culture before antibiotics if bacterial source suspected",
            ],
            "long_term": [
                "Annual flu vaccine — reduces hospitalization risk 40–60%",
                "Immune optimization: vitamin D 4000IU/day, zinc, 7–9h sleep",
                "Recurring fevers → immunology workup to identify underlying predisposition",
            ],
            "risk_level":   "medium",
            "red_flags": [
                "Temperature >39.5°C not responding to antipyretics",
                "Stiff neck or photophobia — meningitis red flag",
                "Petechial rash with fever",
                "Fever after travel to tropical endemic area",
                "Altered consciousness or confusion",
            ],
            "safe_signals": [
                "Low-grade <38.3°C in otherwise healthy adult — likely viral",
                "Fever breaking with sweating and improved subjective energy",
            ],
            "confidence": 0.85,
            "clarity":    "high",
        }

    def _neurological_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "neurology",
            "summary": "Neurological symptom — evaluation and pattern identification",
            "reasoning": (
                "Headache and neurological symptoms span benign tension headache to serious "
                "intracranial pathology. Key differentiator: onset pattern, severity trajectory, "
                "and associated neurological signs."
            ),
            "recommendation": [
                "Rest in quiet, dark room for tension/migraine type — screen avoidance critical",
                "Hydrate: dehydration drives 30% of non-migraine headaches",
                "Urgent evaluation if: sudden 'thunderclap' onset, worst-ever headache, associated neurological deficit",
            ],
            "short_term": [
                "Hydrate 500mL immediately — dehydration is the most common reversible headache trigger",
                "Track: location, character (throbbing/pressure), severity 1–10, duration, triggers",
                "Cold or warm compress based on type — cold for migraine, warm for tension",
            ],
            "mid_term": [
                "Headache diary 4 weeks: identify pattern, triggers, hormonal correlation",
                "CBC, thyroid, blood pressure evaluation to rule out secondary causes",
                "MRI brain without contrast if recurrent severe headaches >1×/week",
            ],
            "long_term": [
                "Address root causes: sleep quality, hydration, posture, screen ergonomics, stress",
                "Magnesium glycinate 400mg/day — Level A evidence for migraine prophylaxis",
                "HRV monitoring for autonomic nervous system health and stress recovery",
            ],
            "risk_level":   "medium",
            "red_flags": [
                "Sudden severe 'thunderclap' headache — worst of life",
                "Headache with fever and stiff neck — meningitis",
                "Progressive worsening over days without clear cause",
                "Associated motor weakness, speech difficulty, or vision loss",
            ],
            "safe_signals": [
                "Gradual onset, tension-type bilateral distribution",
                "Responds to hydration and rest within 1–2h",
                "Known migraine pattern with prior similar episodes",
            ],
            "confidence": 0.80,
            "clarity":    "high",
        }

    def _musculoskeletal_response(self) -> Dict:
        return {
            "urgency": "lifestyle",
            "domain":  "musculoskeletal",
            "summary": "Musculoskeletal — conservative management first line",
            "reasoning": (
                "Musculoskeletal pain is the most common medical complaint globally. "
                "Conservative management resolves 80%+ of cases within 6 weeks. "
                "Key analysis: traumatic vs. atraumatic, neurological involvement, red flags."
            ),
            "recommendation": [
                "Acute (<48h): RICE — Rest, Ice 15min/45min cycle, Compression, Elevation",
                "Subacute (>48h): gentle movement — immobilization beyond 48h delays recovery",
                "Physician if: trauma mechanism, deformity, neurological symptoms (numbness/weakness), no improvement 2 weeks",
            ],
            "short_term": [
                "Anti-inflammatory: ibuprofen 400mg TID with food if not contraindicated",
                "Ice first 48h, then transition to heat for muscle relaxation",
                "Identify and avoid the specific aggravating movement — not all movement",
            ],
            "mid_term": [
                "Physical therapy: 6-week structured program outperforms surgery in non-traumatic cases",
                "Posture and ergonomics audit — 60%+ of back/neck pain has postural root",
                "Sports medicine or orthopedic evaluation if recurrent or athlete",
            ],
            "long_term": [
                "Strength training — stronger muscles protect joints, reduce recurrence 50%",
                "Daily 15-min mobility work — consistency trumps duration",
                "Omega-3 3g/day + turmeric — anti-inflammatory protocol backed by evidence",
            ],
            "risk_level":   "low",
            "red_flags": [
                "Trauma with visible deformity — possible fracture",
                "Night pain waking from sleep — red flag for malignancy or infection",
                "Neurological symptoms: numbness, weakness, incontinence",
                "Fever with joint pain — septic arthritis emergency",
            ],
            "safe_signals": [
                "Pain reproducible with specific posture or movement",
                "Improves with rest and anti-inflammatory",
                "History of identical prior episode with resolution",
            ],
            "confidence": 0.82,
            "clarity":    "high",
        }

    def _fatigue_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "internal_medicine",
            "summary": "Systemic fatigue — multi-factor evaluation recommended",
            "reasoning": (
                "Fatigue has 50+ potential causes. Highest-yield approach: "
                "rule out treatable deficiencies first (iron, B12, D, thyroid), "
                "then evaluate sleep architecture and cortisol dysregulation."
            ),
            "recommendation": [
                "Order: CBC, ferritin, B12, folate, TSH/fT4, vitamin D 25-OH, fasting glucose, hs-CRP",
                "Sleep audit: quantity (target 7–9h), quality (track HRV or use wearable)",
                "Lifestyle audit: caffeine timing, alcohol, screen exposure, exercise intensity balance",
            ],
            "short_term": [
                "Optimize sleep immediately: consistent schedule, room 18–20°C, no screens 1h before",
                "Iron + vitamin D are the two most common reversible causes — test before supplementing",
                "Reduce caffeine after 1pm — it masks fatigue without resolving it",
            ],
            "mid_term": [
                "Full hormonal panel: cortisol AM, testosterone (male), progesterone/estradiol (female)",
                "Sleep study if snoring, gasping, or non-restorative sleep suspected",
                "Psychological stress audit — cortisol dysregulation is #2 cause of chronic fatigue",
            ],
            "long_term": [
                "HRV baseline — objective nervous system health and recovery marker",
                "Progressive aerobic exercise protocol — builds mitochondrial density, reverses fatigue",
                "Annual comprehensive metabolic panel to catch drift before it becomes chronic",
            ],
            "risk_level":   "medium",
            "red_flags": [
                "Unexplained weight loss >5% body weight",
                "Night sweats",
                "Fatigue with lymphadenopathy",
                "Progressive worsening over months despite lifestyle changes",
            ],
            "safe_signals": [
                "Temporal correlation with major stress or workload peak",
                "Improves substantially with vacation/rest period",
                "Correctable deficiency identified (low ferritin, low D)",
            ],
            "confidence": 0.80,
            "clarity":    "high",
        }

    def _gi_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "gastroenterology",
            "summary": "GI symptoms — functional evaluation first",
            "reasoning": (
                "Most GI symptoms in healthy adults are functional (IBS, GERD, dietary intolerance). "
                "The elimination protocol resolves 60–70% without medication."
            ),
            "recommendation": [
                "Elimination protocol: remove ultra-processed food, alcohol, caffeine for 2 weeks",
                "Food and symptom journal: log what, when, quantity, and resulting symptoms",
                "Physician if: blood in stool, unintentional weight loss, symptoms >4 weeks",
            ],
            "short_term": [
                "Eat slowly, smaller portions — improves 70% of functional GI symptoms",
                "Probiotics: Lactobacillus + Bifidobacterium blend 4–6 weeks",
                "Identify trigger foods via elimination — not via assumption",
            ],
            "mid_term": [
                "H. pylori breath test if epigastric pain or prior NSAID use",
                "Celiac serology (IgA anti-tTG) if bloating + fatigue + nutritional deficiencies",
                "Endoscopy/colonoscopy if symptoms persist >4 weeks or red flags present",
            ],
            "long_term": [
                "Gut microbiome optimization: fermented foods, diverse fiber >30g/day",
                "Gut-brain axis: stress management measurably reduces GI symptoms",
                "Colonoscopy screening from age 45 — earlier if family history",
            ],
            "risk_level":   "low",
            "red_flags": [
                "Blood in stool (bright red or dark tarry melena)",
                "Unexplained weight loss",
                "Dysphagia — difficulty swallowing",
                "Symptoms that wake you from sleep",
            ],
            "safe_signals": [
                "Symptoms correlate clearly with specific foods",
                "Stress-related temporal pattern",
                "Improvement with dietary changes within 2 weeks",
            ],
            "confidence": 0.78,
            "clarity":    "high",
        }

    def _mental_health_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "psychiatry_psychology",
            "summary": "Mental health signal — structured evidence-based support",
            "reasoning": (
                "Anxiety, stress, and mood disorders are among the most undertreated conditions globally. "
                "Effective, evidence-based interventions exist. The goal is not symptom suppression "
                "but building genuine resilience."
            ),
            "recommendation": [
                "Consult a licensed psychologist or psychiatrist — CBT is first-line evidence-based treatment",
                "Immediate relief: structured breathing (4-7-8 technique), cold exposure, physical movement",
                "Never self-medicate with substances — amplifies the problem medium-term",
            ],
            "short_term": [
                "4-7-8 breathing: inhale 4s, hold 7s, exhale 8s — activates parasympathetic system immediately",
                "30-min daily outdoor walk — proven equivalent to medication for mild-moderate depression",
                "Reduce decision fatigue: simplify choices, build routines to lower cognitive load",
            ],
            "mid_term": [
                "CBT with licensed therapist: 8–16 sessions produce substantial measurable improvement",
                "Sleep hygiene priority — most mental health conditions are significantly worsened by poor sleep",
                "Social connection: isolation is the single biggest risk amplifier for mood disorders",
            ],
            "long_term": [
                "HRV-guided training for autonomic nervous system resilience — measurable marker",
                "Daily mindfulness 10min: longitudinal studies show cortisol reduction and regulation improvement",
                "Annual mental health check-in — preventive, not only crisis-driven",
            ],
            "risk_level":   "medium",
            "red_flags": [
                "Suicidal ideation — seek immediate care, call crisis line (106 Colombia)",
                "Unable to perform daily functions for >2 consecutive weeks",
                "Substance use as primary coping mechanism",
            ],
            "safe_signals": [
                "Situational with clear external trigger that is resolving",
                "Functional — can work and maintain key relationships",
                "Responds to exercise and sleep improvement within 1–2 weeks",
            ],
            "confidence": 0.80,
            "clarity":    "high",
        }

    def _longevity_response(self) -> Dict:
        return {
            "urgency": "prevention",
            "domain":  "longevity_medicine",
            "summary": "Longevity optimization — evidence-based protocol",
            "reasoning": (
                "The highest-ROI longevity interventions are well-established and compound over decades: "
                "sleep, exercise (especially Zone 2 + strength), nutrition quality, and stress management. "
                "Biomarker baseline enables early detection before symptoms appear."
            ),
            "recommendation": [
                "Baseline biomarkers: ApoB, Lp(a), fasting insulin, HbA1c, homocysteine, hs-CRP, testosterone, ferritin",
                "Zone 2 cardio 3h/week minimum — builds mitochondrial density and metabolic flexibility",
                "Strength training 2–3×/week — strongest predictor of all-cause mortality in longitudinal studies",
            ],
            "short_term": [
                "Full blood panel including ApoB (not just LDL) — far better cardiovascular predictor",
                "Start Zone 2 cardio: 30–45min sessions at conversational pace, 3×/week",
                "Protein target: 1.6–2.0g/kg/day — most people significantly under-eat protein",
            ],
            "mid_term": [
                "VO2max test — strongest single predictor of all-cause longevity in any modality",
                "CGM (continuous glucose monitor) trial 2 weeks — understand personal metabolic response",
                "DEXA scan: body composition baseline — muscle mass and visceral fat are the metrics",
            ],
            "long_term": [
                "Annual whole-body MRI for early cancer detection — available in Colombia at premium centers",
                "Coronary calcium score at age 40–45 for cardiovascular risk stratification",
                "Muscle mass preservation: the longevity insurance policy — build early, protect relentlessly",
            ],
            "risk_level":   "low",
            "red_flags": [
                "ApoB >130 mg/dL — silent cardiovascular risk",
                "HbA1c approaching 5.7% — pre-diabetes threshold",
                "Declining VO2max year over year",
                "Visceral fat area increasing on DEXA",
            ],
            "safe_signals": [
                "Consistent weekly exercise exceeding 150 min moderate/75 min vigorous",
                "Stable quality sleep with HRV maintenance",
                "Controlled biomarkers within optimal ranges",
            ],
            "confidence": 0.88,
            "clarity":    "high",
        }

    def _general_response(self) -> Dict:
        return {
            "urgency": "monitor",
            "domain":  "general_medicine",
            "summary": "General health query — provide specific symptoms for targeted triage",
            "reasoning": "Insufficient symptom specificity for targeted triage. General preventive framework provided.",
            "recommendation": [
                "Describe symptoms precisely: location, character, duration, severity 1–10, triggers",
                "Consult a licensed physician for proper diagnosis and treatment plan",
                "Seek immediate care if symptoms are sudden, severe, or rapidly worsening",
            ],
            "short_term": [
                "Document your symptoms with timing and context before the physician visit",
                "Book GP appointment within 1 week for non-urgent concerns",
            ],
            "mid_term": [
                "Annual comprehensive health check is the standard of preventive care",
                "Review the four pillars: sleep quality, stress level, nutrition, and exercise",
            ],
            "long_term": [
                "Establish a preventive medicine relationship with a physician you trust",
                "Build a personal health baseline with annual biomarkers",
            ],
            "risk_level":   "low",
            "red_flags": [
                "Sudden severe onset of any symptom",
                "Any neurological deficit (weakness, speech, vision)",
                "Chest pain or difficulty breathing",
            ],
            "safe_signals": ["Gradual onset, stable, not worsening"],
            "confidence": 0.60,
            "clarity":    "low",
        }
