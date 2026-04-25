from __future__ import annotations

from typing import Any, Dict, List


class MedicalSupremeEngine:

    DISCLAIMER = (
        "This is not medical advice. Always consult a licensed physician "
        "before acting on any health-related information."
    )

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Primary entry point — compatible with AgentOrchestratorPro._try_methods().
        Wraps symptom_triage() and enriches the response for downstream LLM synthesis.
        """
        triage_result = self.symptom_triage(query)

        return {
            "query":           query,
            "triage":          triage_result.get("triage", "general evaluation needed"),
            "recommendation":  triage_result.get("recommendation", [
                "Describe your symptoms in detail for a better triage",
                "Consult a licensed physician for a proper diagnosis",
                "If symptoms are severe or sudden, seek immediate care",
            ]),
            "disclaimer":      self.DISCLAIMER,
            "source":          "medical_supreme",
        }

    def symptom_triage(self, symptoms: str) -> Dict[str, Any]:
        symptoms = (symptoms or "").lower()

        if any(w in symptoms for w in ["fever", "fiebre", "temperatura alta"]):
            return {
                "triage": "possible infection",
                "recommendation": [
                    "Monitor body temperature every 4 hours",
                    "Rest and stay well hydrated",
                    "Consider medical consultation if fever exceeds 38.5°C or persists > 48h",
                ],
            }

        if (
            "palpitaciones" in symptoms
            or "chest pain" in symptoms
            or "dolor de pecho" in symptoms
            or ("pecho" in symptoms and "dolor" in symptoms)
            or ("chest" in symptoms and ("pain" in symptoms or "tight" in symptoms or "pressure" in symptoms))
        ):
            return {
                "triage": "urgent — cardiac or pulmonary",
                "recommendation": [
                    "Seek urgent medical evaluation immediately",
                    "Do not delay — call emergency services if pain is severe",
                ],
            }

        if any(w in symptoms for w in ["headache", "dolor cabeza", "migraña", "migraine"]):
            return {
                "triage": "neurological evaluation recommended",
                "recommendation": [
                    "Rest in a quiet, dark room",
                    "Hydrate and avoid screens",
                    "Consult a physician if headaches are recurrent or accompanied by vision changes",
                ],
            }

        if any(w in symptoms for w in ["fatiga", "fatigue", "cansancio", "tired", "exhausted"]):
            return {
                "triage": "systemic — multiple possible causes",
                "recommendation": [
                    "Evaluate sleep quality and duration",
                    "Check nutrition and iron levels",
                    "Consider a complete blood panel (CBC, thyroid, vitamin D, B12)",
                ],
            }

        return {
            "triage": "general evaluation needed",
            "recommendation": [
                "Provide more specific symptoms for a targeted triage",
                "Consult a licensed physician for diagnosis and treatment",
            ],
        }
