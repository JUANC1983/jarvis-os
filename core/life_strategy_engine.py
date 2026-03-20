class LifeStrategyEngine:

    def plan(self,age,goals):

        strategy={}

        if age<35:

            strategy["focus"]="aggressive growth"

        elif age<50:

            strategy["focus"]="wealth consolidation"

        else:

            strategy["focus"]="capital preservation"

        strategy["goals"]=goals

        return strategy
