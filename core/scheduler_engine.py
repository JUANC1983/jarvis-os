from apscheduler.schedulers.background import BackgroundScheduler


class JarvisScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def status(self):
        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "next_run": str(job.next_run_time),
                }
                for job in self.scheduler.get_jobs()
            ],
        }
