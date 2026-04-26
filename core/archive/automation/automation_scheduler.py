from apscheduler.schedulers.background import BackgroundScheduler
from core.intelligence_automation_pipeline import IntelligenceAutomationPipeline
from core.audit_engine import AuditEngine

class JarvisAutomationScheduler:

    def __init__(self):

        self.scheduler=BackgroundScheduler()

        self.pipeline=IntelligenceAutomationPipeline()

        self.audit=AuditEngine()

    def start(self):

        if not self.scheduler.running:

            self.scheduler.add_job(
                self.run_intelligence_pipeline,
                "interval",
                minutes=20,
                id="intelligence_pipeline"
            )

            self.scheduler.add_job(
                self.run_alert_monitor,
                "interval",
                minutes=5,
                id="alert_monitor"
            )

            self.scheduler.start()

            self.audit.log_event("scheduler_started",{"status":"running"})


    def run_intelligence_pipeline(self):

        result=self.pipeline.run()

        self.audit.log_event("pipeline_run",result)


    def run_alert_monitor(self):

        alerts=self.pipeline.alerts.evaluate()

        self.audit.log_event("alert_monitor_run",alerts)


    def status(self):

        return{
            "running":self.scheduler.running,
            "jobs":[
                {
                    "id":job.id,
                    "next_run":str(job.next_run_time)
                }
                for job in self.scheduler.get_jobs()
            ]
        }
