from celery import Celery
from .config import settings

# Create Celery app
celery_app = Celery(
    "docker_update_orchestrator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.discovery",
        "app.tasks.updates",
        "app.tasks.health_checks",
        "app.tasks.notifications",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "scan-all-servers": {
        "task": "app.tasks.discovery.scan_all_servers",
        "schedule": settings.UPDATE_CHECK_INTERVAL_HOURS * 3600.0,  # Convert hours to seconds
    },
    "check-all-updates": {
        "task": "app.tasks.updates.check_all_updates",
        "schedule": settings.UPDATE_CHECK_INTERVAL_HOURS * 3600.0,
    },
    "daily-digest": {
        "task": "app.tasks.notifications.send_daily_digest",
        "schedule": 86400.0,  # Once per day
    },
}
