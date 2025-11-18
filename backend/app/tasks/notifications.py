from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..core.config import settings
from ..models import Update, UpdateStatus, Container
from ..services.notification_service import notification_service
import logging
import asyncio

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.notifications.send_daily_digest")
def send_daily_digest():
    """Send daily digest of updates"""
    asyncio.run(_send_daily_digest_async())


async def _send_daily_digest_async():
    """Async implementation of send_daily_digest"""
    async with async_session_maker() as session:
        try:
            # Count pending updates
            pending_result = await session.execute(
                select(Update).where(Update.status == UpdateStatus.PENDING)
            )
            pending_count = len(pending_result.scalars().all())

            # Count critical updates (high/critical risk)
            critical_result = await session.execute(
                select(Update).where(
                    Update.status == UpdateStatus.PENDING,
                    Update.risk_level.in_(["high", "critical"])
                )
            )
            critical_count = len(critical_result.scalars().all())

            # Count containers with updates available
            updates_result = await session.execute(
                select(Container).where(Container.update_available == True)
            )
            updates_count = len(updates_result.scalars().all())

            # Send digest
            await notification_service.send_daily_digest(
                updates_count=updates_count,
                critical_count=critical_count,
                pending_approvals=pending_count
            )

            logger.info("Daily digest sent")

        except Exception as e:
            logger.error(f"Error sending daily digest: {str(e)}")
