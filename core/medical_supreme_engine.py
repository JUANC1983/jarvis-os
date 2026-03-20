class MedicalSupremeEngine:

    def symptom_triage(self, symptoms):

        symptoms = symptoms.lower()

        if "fever" in symptoms or "fiebre" in symptoms:

            return {
                "triage":"possible infection",
                "recommendation":[
                    "monitor temperature",
                    "rest",
                    "hydrate",
                    "consider medical consultation"
                ]
            }

        if "chest pain" in symptoms or "dolor pecho" in symptoms:

            return {
                "triage":"urgent",
                "recommendation":[
                    "seek urgent medical evaluation"
                ]
            }

        return {"status":"insufficient data"}

