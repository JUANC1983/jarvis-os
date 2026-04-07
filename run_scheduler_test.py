from core.scheduler_engine import JarvisScheduler
from core.meetings_jobs import cleanup_meetings_job

scheduler = JarvisScheduler()
scheduler.start()

scheduler.scheduler.add_job(
    cleanup_meetings_job,
    'interval',
    minutes=5
)

print("Scheduler running...")
input()
