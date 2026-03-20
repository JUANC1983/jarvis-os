import subprocess
import webbrowser
import os

class JarvisOperator:

    def open_app(self,name):

        apps = {

            "chrome":"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge":"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "notepad":"notepad.exe",
            "explorer":"explorer.exe"

        }

        if name in apps:

            subprocess.Popen(apps[name])

            return {"status":"opened","app":name}

        return {"status":"unknown_app"}


    def open_url(self,url):

        webbrowser.open(url)

        return {"status":"opened","url":url}


    def run_command(self,cmd):

        result = subprocess.run(cmd,shell=True,capture_output=True,text=True)

        return {

            "stdout":result.stdout,
            "stderr":result.stderr

        }
