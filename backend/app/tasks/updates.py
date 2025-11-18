from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..core.config import settings
from ..models import Container, Update, UpdateStatus, UpdateType, ChangelogAnalysis, RiskLevel
from ..services.registry_service import registry_service
from ..services.changelog_service import changelog_service
from ..services.llm_service import llm_service
from ..services.notification_service import notification_service
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.updates.check_all_updates")
def check_all_updates():
    """Check for updates for all containers"""
    asyncio.run(_check_all_updates_async())


async def _check_all_updates_async():
    """Async implementation of check_all_updates"""
    async with async_session_maker() as session:
        try:
            # Get all running containers
            result = await session.execute(
                select(Container).where(Container.is_running == True)
            )
            containers = result.scalars().all()

            logger.info(f"Checking updates for {len(containers)} containers")

            for container in containers:
                try:
                    await _check_container_update(container, session)
                except Exception as e:
                    logger.error(f"Error checking updates for {container.container_name}: {str(e)}")

            await session.commit()
            logger.info("Update check completed")

        except Exception as e:
            logger.error(f"Error in check_all_updates: {str(e)}")
            await session.rollback()


async def _check_container_update(container: Container, session: AsyncSession):
    """Check for updates for a single container"""
    if not container.registry or not container.repository or not container.tag:
        logger.warning(f"Incomplete image info for {container.container_name}")
        return

    # Skip :latest tags
    if container.tag == "latest":
        logger.debug(f"Skipping {container.container_name} with :latest tag")
        return

    logger.info(f"Checking updates for {container.container_name}")

    # Check registry for updates
    update_info = await registry_service.check_for_updates(
        registry=container.registry,
        repository=container.repository,
        current_tag=container.tag
    )

    if not update_info:
        logger.warning(f"Could not check updates for {container.container_name}")
        return

    container.last_update_check = datetime.utcnow()

    if update_info["update_available"]:
        logger.info(f"Update available for {container.container_name}: {update_info['latest_tag']}")

        container.update_available = True
        container.latest_version = update_info["latest_tag"]

        # Check if update already exists
        result = await session.execute(
            select(Update).where(
                Update.container_id == container.id,
                Update.to_version == update_info["latest_tag"],
                Update.status.in_([UpdateStatus.PENDING, UpdateStatus.APPROVED])
            )
        )
        existing_update = result.scalar_one_or_none()

        if not existing_update:
            # Create new update record
            update = Update(
                container_id=container.id,
                from_version=container.tag,
                to_version=update_info["latest_tag"],
                from_image=container.image,
                to_image=f"{container.registry}/{container.repository}:{update_info['latest_tag']}",
                from_digest=container.digest,
                to_digest=update_info.get("latest_digest"),
                update_type=UpdateType(update_info.get("update_type", "unknown")),
                status=UpdateStatus.PENDING
            )
            session.add(update)
            await session.flush()  # Get update ID

            # Analyze changelog
            await _analyze_changelog(container, update, session)

            # Send notification
            await notification_service.send_update_available(
                container_name=container.container_name,
                server_name=container.server.name if container.server else "Unknown",
                from_version=container.tag,
                to_version=update_info["latest_tag"],
                risk_level=update.risk_level or "unknown",
                breaking_changes=update.has_breaking_changes or False
            )

    else:
        container.update_available = False
        container.latest_version = None


async def _analyze_changelog(container: Container, update: Update, session: AsyncSession):
    """Analyze changelog for an update"""
    try:
        logger.info(f"Analyzing changelog for {container.container_name}")

        # Get changelog
        changelog_data = await changelog_service.get_changelog(
            image_name=f"{container.repository}",
            from_version=update.from_version,
            to_version=update.to_version
        )

        if not changelog_data:
            logger.warning(f"Could not retrieve changelog for {container.container_name}")
            return

        # Analyze with LLM
        analysis = await llm_service.analyze_changelog(
            image_name=container.image,
            from_version=update.from_version,
            to_version=update.to_version,
            changelog=changelog_data["raw_changelog"]
        )

        if not analysis:
            logger.warning(f"Could not analyze changelog for {container.container_name}")
            return

        # Store changelog analysis
        changelog_analysis = ChangelogAnalysis(
            image_name=container.image,
            from_version=update.from_version,
            to_version=update.to_version,
            changelog_url=changelog_data.get("url"),
            changelog_source=changelog_data.get("source"),
            raw_changelog=changelog_data.get("raw_changelog"),
            llm_provider=analysis["llm_provider"],
            llm_model=analysis["llm_model"],
            executive_summary=analysis.get("executive_summary"),
            has_breaking_changes=analysis.get("has_breaking_changes", False),
            breaking_changes=analysis.get("breaking_changes", []),
            config_changes_required=analysis.get("config_changes_required", []),
            risk_level=RiskLevel(analysis.get("risk_level", "medium")),
            safe_to_auto_update=analysis.get("safe_to_auto_update", False),
            deprecated_features=analysis.get("deprecated_features", []),
            removed_features=analysis.get("removed_features", []),
            new_features=analysis.get("new_features", []),
            improvements=analysis.get("improvements", []),
            bug_fixes=analysis.get("bug_fixes", []),
            security_fixes=analysis.get("security_fixes", []),
            dependency_updates=analysis.get("dependency_updates", []),
            minimum_version_requirements=analysis.get("minimum_version_requirements", {}),
            action_items=analysis.get("action_items", []),
            testing_recommendations=analysis.get("testing_recommendations", []),
            estimated_update_time_minutes=analysis.get("estimated_update_time_minutes"),
            rollback_complexity=analysis.get("rollback_complexity"),
            recommended_action=analysis.get("recommended_action"),
            requires_human_review=analysis.get("requires_human_review", False),
            human_review_reason=analysis.get("human_review_reason")
        )
        session.add(changelog_analysis)
        await session.flush()

        # Update update record
        update.changelog_id = changelog_analysis.id
        update.changelog_summary = analysis.get("executive_summary")
        update.breaking_changes = analysis.get("breaking_changes", [])
        update.config_changes_required = analysis.get("config_changes_required", [])
        update.action_items = analysis.get("action_items", [])
        update.risk_level = analysis.get("risk_level", "medium")
        update.risk_factors = analysis.get("risk_factors", [])
        update.safe_to_auto_update = analysis.get("safe_to_auto_update", False)
        update.requires_downtime = analysis.get("requires_downtime", False)
        update.estimated_downtime_seconds = (
            analysis.get("estimated_downtime_minutes", 0) * 60
            if analysis.get("estimated_downtime_minutes")
            else None
        )
        update.is_security_update = len(analysis.get("security_fixes", [])) > 0

        logger.info(f"Changelog analysis completed for {container.container_name}")

    except Exception as e:
        logger.error(f"Error analyzing changelog: {str(e)}")


@shared_task(name="app.tasks.updates.execute_update")
def execute_update(update_id: str):
    """Execute a container update"""
    asyncio.run(_execute_update_async(update_id))


async def _execute_update_async(update_id: str):
    """Async implementation of execute_update"""
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(Update).where(Update.id == update_id)
            )
            update = result.scalar_one_or_none()

            if not update:
                logger.error(f"Update {update_id} not found")
                return

            # TODO: Implement actual update execution logic
            # This would involve:
            # 1. Pull new image
            # 2. Stop old container
            # 3. Create backup if configured
            # 4. Start new container
            # 5. Run health checks
            # 6. Rollback if health checks fail

            logger.info(f"Update execution placeholder for update {update_id}")

        except Exception as e:
            logger.error(f"Error executing update {update_id}: {str(e)}")
            await session.rollback()


@shared_task(name="app.tasks.updates.check_container_update")
def check_container_update(container_id: str):
    """Check for updates for a specific container"""
    asyncio.run(_check_container_update_by_id(container_id))


async def _check_container_update_by_id(container_id: str):
    """Async implementation of check_container_update"""
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(Container).where(Container.id == container_id)
            )
            container = result.scalar_one_or_none()

            if not container:
                logger.error(f"Container {container_id} not found")
                return

            await _check_container_update(container, session)
            await session.commit()

        except Exception as e:
            logger.error(f"Error checking update for container {container_id}: {str(e)}")
            await session.rollback()
