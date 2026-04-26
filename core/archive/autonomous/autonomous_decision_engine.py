class AutonomousDecisionEngine:

    def decide(self,task):

        task = task.lower()

        if "linkedin" in task or "trabajo" in task:

            return "linkedin_agent"

        if "abrir" in task or "open" in task:

            return "computer_control"

        if "imagen" in task or "image" in task:

            return "image_generation"

        if "video" in task:

            return "video_analysis"

        if "golf" in task:

            return "golf_agent"

        if "accion" in task or "stock" in task:

            return "trader"

        return "conversation"
