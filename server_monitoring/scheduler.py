import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from server_monitoring.database import cleanup_old_metrics

def start_scheduler():
    # Используем pytz.utc
    scheduler = BackgroundScheduler(timezone=pytz.utc)

    # Каждую ночь в 00:00 UTC
    scheduler.add_job(cleanup_old_metrics, 'cron', hour=0, minute=0)

    scheduler.start()
    return scheduler
