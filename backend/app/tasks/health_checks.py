from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.health_checks.run_health_check")
def run_health_check(container_id: str):
    """Run health check for a container"""
    logger.info(f"Health check placeholder for container {container_id}")
    # TODO: Implement health check logic
    pass
