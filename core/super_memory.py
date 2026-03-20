import json
import os
from datetime import datetime


class SuperMemory:

    def __init__(self):

        self.file="data/super_memory.json"

        os.makedirs("data",exist_ok=True)

        if not os.path.exists(self.file):

            with open(self.file,"w") as f:
                json.dump([],f)

    def remember(self,entry):

        memories=self.load()

        memories.append({
            "timestamp":datetime.utcnow().isoformat(),
            "entry":entry
        })

        with open(self.file,"w") as f:
            json.dump(memories,f,indent=2)

    def load(self):

        with open(self.file,"r") as f:
            return json.load(f)

    def search(self,keyword):

        memories=self.load()

        return [m for m in memories if keyword.lower() in str(m).lower()]
