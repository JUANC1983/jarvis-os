import requests
import json

class GlobalGolfCourseImporter:

    def download_dataset(self):

        url="https://raw.githubusercontent.com/martinjc/golf-courses/master/golf-courses.json"

        data=requests.get(url).json()

        return data

    def save(self):

        data=self.download_dataset()

        with open("data/golf/global_courses.json","w",encoding="utf-8") as f:

            json.dump(data,f)

        return {"courses":len(data)}

