class AutonomousAgent:

    def __init__(self):
        self.tasks=[]

    def add_task(self,task):

        self.tasks.append(task)

    def run(self):

        for task in self.tasks:

            print("Executing:",task)