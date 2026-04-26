from datetime import datetime

class AutomationEngine:

    def __init__(self,audit_engine):
        self.audit=audit_engine

    def run_pipeline(self,pipeline_name:str,payload:dict):

        event={
            "pipeline":pipeline_name,
            "payload":payload,
            "timestamp":datetime.utcnow().isoformat()
        }

        self.audit.log_event("automation_pipeline_run",event)

        return {
            "status":"completed",
            "pipeline":pipeline_name,
            "timestamp":event["timestamp"]
        }
