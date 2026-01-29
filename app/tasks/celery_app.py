"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "trademark_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.notification_tasks",
        "app.tasks.sync_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=540,  # 9 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Check for expiring trademarks daily at 9 AM Moscow time
    "check-expiring-trademarks": {
        "task": "check_expiring_trademarks",
        "schedule": crontab(hour=9, minute=0),
    },
    # Send daily summary at 10 AM Moscow time
    "send-daily-summary": {
        "task": "send_daily_summary",
        "schedule": crontab(hour=10, minute=0),
    },
    # Sync with FIPS daily at 3 AM Moscow time
    "sync-fips-daily": {
        "task": "sync_fips_trademarks",
        "schedule": crontab(hour=3, minute=0),
    },
    # Sync with WIPO daily at 4 AM Moscow time
    "sync-wipo-daily": {
        "task": "sync_wipo_trademarks",
        "schedule": crontab(hour=4, minute=0),
    },
    # Sync priority registrations (expiring soon) twice daily
    "sync-priority-morning": {
        "task": "sync_priority_registrations",
        "schedule": crontab(hour=6, minute=0),
    },
    "sync-priority-evening": {
        "task": "sync_priority_registrations",
        "schedule": crontab(hour=18, minute=0),
    },
    # Weekly full reconciliation on Sunday at 2 AM
    "weekly-reconciliation": {
        "task": "full_reconciliation",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
    },
}
