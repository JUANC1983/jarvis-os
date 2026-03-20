import subprocess
import webbrowser
import os

class ComputerControlAgent:

    def open_app(self, app):

        apps = {
            "chrome": "C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge": "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "notepad": "notepad.exe",
            "explorer": "explorer.exe"
        }

        if app in apps:

            subprocess.Popen(apps[app])

            return {
                "status": "opened",
                "app": app
            }

        return {
            "status": "unknown_app",
            "app": app
        }


    def open_url(self, url):

        webbrowser.open(url)

        return {
            "status": "opened",
            "url": url
        }


    def run_command(self, cmd):

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr
        }
