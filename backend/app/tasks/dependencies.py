from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..core.config import settings
from ..models import Server
from ..services.dependency_service import dependency_service
import logging
import asyncio

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.dependencies.analyze_all_dependencies")
def analyze_all_dependencies():
    """Analyze dependencies for all containers"""
    asyncio.run(_analyze_all_dependencies_async())


async def _analyze_all_dependencies_async():
    """Async implementation of analyze_all_dependencies"""
    async with async_session_maker() as session:
        try:
            logger.info("Starting dependency analysis for all containers")

            count = await dependency_service.analyze_all_dependencies(session)

            logger.info(f"Dependency analysis completed. Found {count} dependencies")

        except Exception as e:
            logger.error(f"Error in analyze_all_dependencies: {str(e)}")
            await session.rollback()


@shared_task(name="app.tasks.dependencies.analyze_server_dependencies")
def analyze_server_dependencies(server_id: str):
    """Analyze dependencies for a specific server"""
    asyncio.run(_analyze_server_dependencies_async(server_id))


async def _analyze_server_dependencies_async(server_id: str):
    """Async implementation of analyze_server_dependencies"""
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(Server).where(Server.id == server_id)
            )
            server = result.scalar_one_or_none()

            if not server:
                logger.error(f"Server {server_id} not found")
                return

            logger.info(f"Analyzing dependencies for server {server.name}")

            count = await dependency_service.analyze_all_dependencies(session, server_id=server_id)

            logger.info(f"Found {count} dependencies on {server.name}")

        except Exception as e:
            logger.error(f"Error analyzing dependencies for server {server_id}: {str(e)}")
            await session.rollback()
