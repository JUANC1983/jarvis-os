class GeopoliticalRiskEngine:

    def analyze(self,text):

        risks=[]

        text=text.lower()

        if "iran" in text or "israel" in text:
            risks.append("Middle East conflict escalation")

        if "taiwan" in text or "china" in text:
            risks.append("US China geopolitical tension")

        if "oil" in text or "petroleo" in text:
            risks.append("Energy supply shock risk")

        if "war" in text or "guerra" in text:
            risks.append("Global conflict escalation")

        return risks
