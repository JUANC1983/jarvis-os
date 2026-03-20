class FitnessPerformanceEngine:

    def microcycle(self):

        return {
            "plan":[
                "strength training",
                "mobility",
                "cardio zone2",
                "recovery"
            ]
        }

    def nutrition(self,weight):

        protein = weight * 1.8

        return {
            "protein_target":protein,
            "note":"adjust calories depending goal"
        }
