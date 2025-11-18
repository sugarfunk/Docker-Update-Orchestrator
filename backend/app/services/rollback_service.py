from typing import Tuple, Optional
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models import (
    Rollback, RollbackReason, Update, Container, Server, UpdateStatus
)
from .docker_service import docker_service
from .backup_service import backup_service
from .health_check_service import health_check_service

logger = logging.getLogger(__name__)


class RollbackService:
    """Service for executing rollbacks after failed updates"""

    def __init__(self):
        self.max_rollback_retries = 3

    async def execute_rollback(
        self,
        update_id: str,
        reason: RollbackReason,
        session: AsyncSession,
        triggered_by: str = "system"
    ) -> Tuple[bool, str]:
        """Execute complete rollback process"""
        try:
            # Get update
            result = await session.execute(
                select(Update).where(Update.id == update_id)
            )
            update = result.scalar_one_or_none()

            if not update:
                return False, "Update not found"

            # Get container
            container_result = await session.execute(
                select(Container).where(Container.id == update.container_id)
            )
            container = container_result.scalar_one_or_none()

            if not container:
                return False, "Container not found"

            # Get server
            server_result = await session.execute(
                select(Server).where(Server.id == container.server_id)
            )
            server = server_result.scalar_one_or_none()

            if not server:
                return False, "Server not found"

            # Check if rollback already exists
            existing_rollback = await session.execute(
                select(Rollback).where(Rollback.update_id == update_id)
            )
            rollback = existing_rollback.scalar_one_or_none()

            if not rollback:
                # Create rollback record
                rollback = Rollback(
                    update_id=update_id,
                    container_id=container.id,
                    reason=reason,
                    triggered_by=triggered_by,
                    rolled_back_from=update.to_version,
                    rolled_back_to=update.from_version,
                    from_image=update.to_image,
                    to_image=update.from_image,
                    status="in_progress",
                    previous_container_config=update.previous_container_config,
                    backup_path=update.backup_path
                )
                session.add(rollback)
                await session.commit()

            logger.info(f"Starting rollback: {container.container_name} {update.to_version} -> {update.from_version}")
            logger.info(f"Reason: {reason.value}")

            rollback.started_at = datetime.utcnow()
            rollback.current_step = "Stopping current container"
            await session.commit()

            # STEP 1: Stop current (failed) container
            logger.info("Step 1: Stopping current container")

            success, message = docker_service.stop_container(
                server.hostname,
                container.container_id,
                timeout=30
            )

            if not success:
                logger.warning(f"Failed to stop container: {message}")
                # Continue anyway

            rollback.progress_percent = 20
            await session.commit()

            # STEP 2: Remove failed container
            logger.info("Step 2: Removing failed container")
            rollback.current_step = "Removing failed container"
            await session.commit()

            docker_service.remove_container(server.hostname, container.container_id, force=True)

            rollback.progress_percent = 40
            await session.commit()

            # STEP 3: Restore from backup or previous config
            logger.info("Step 3: Restoring previous configuration")
            rollback.current_step = "Restoring previous configuration"
            await session.commit()

            if rollback.backup_path:
                # Restore from backup
                success = await backup_service.restore_backup(
                    rollback.backup_path,
                    container,
                    server
                )

                if success:
                    rollback.backup_restored = True
                    rollback.config_restored = True
                    logger.info("Restored from backup")
                else:
                    logger.warning("Backup restoration failed, using saved config")

            # Use previous config if backup restore failed or no backup
            if not rollback.config_restored and rollback.previous_container_config:
                prev_config = rollback.previous_container_config
                container.image = prev_config.get('image')
                container.image_id = prev_config.get('image_id')
                container.environment_vars = prev_config.get('environment')
                container.volumes = prev_config.get('volumes')
                container.networks = prev_config.get('networks')
                container.ports = prev_config.get('ports')
                container.command = prev_config.get('command')
                container.entrypoint = prev_config.get('entrypoint')
                rollback.config_restored = True

            rollback.progress_percent = 60
            await session.commit()

            # STEP 4: Pull previous image (if needed)
            logger.info("Step 4: Ensuring previous image is available")
            rollback.current_step = "Pulling previous image"
            await session.commit()

            success, message = docker_service.pull_image(server.hostname, rollback.to_image)

            if not success:
                logger.warning(f"Failed to pull previous image: {message}")
                # Continue anyway, image might already exist

            rollback.progress_percent = 70
            await session.commit()

            # STEP 5: Create container with previous version
            logger.info("Step 5: Creating container with previous version")
            rollback.current_step = "Creating previous container"
            await session.commit()

            # Prepare container configuration
            container_config = {
                'name': container.container_name,
                'environment': container.environment_vars,
                'volumes': self._format_volumes(container.volumes),
                'network': container.networks[0] if container.networks else None,
                'ports': self._format_ports(container.ports),
                'restart_policy': {'Name': 'unless-stopped'},
                'detach': True
            }

            if container.command:
                try:
                    container_config['command'] = eval(container.command)
                except:
                    pass

            success, message, new_container_id = docker_service.create_container(
                server.hostname,
                rollback.to_image,
                **container_config
            )

            if not success:
                rollback.status = "failed"
                rollback.error_message = f"Failed to create container: {message}"
                rollback.successful = False
                await session.commit()
                logger.error(f"Rollback failed: {message}")
                return False, f"Failed to create container: {message}"

            logger.info(f"Container created: {new_container_id}")

            rollback.progress_percent = 80
            await session.commit()

            # STEP 6: Start container
            logger.info("Step 6: Starting previous container")
            rollback.current_step = "Starting previous container"
            await session.commit()

            success, message = docker_service.start_container(server.hostname, new_container_id)

            if not success:
                rollback.status = "failed"
                rollback.error_message = f"Failed to start container: {message}"
                rollback.successful = False
                await session.commit()
                logger.error(f"Rollback failed: {message}")
                return False, f"Failed to start container: {message}"

            # Update container record
            container.container_id = new_container_id
            container.image = rollback.to_image
            container.tag = rollback.rolled_back_to
            await session.commit()

            logger.info("Container started successfully")

            rollback.progress_percent = 90
            await session.commit()

            # STEP 7: Health check
            logger.info("Step 7: Running health check")
            rollback.current_step = "Running health check"
            await session.commit()

            # Wait a bit for container to start
            import asyncio
            await asyncio.sleep(10)

            health_check = await health_check_service.run_health_check(
                container=container,
                server=server,
                session=session
            )

            rollback.health_check_passed = health_check.is_healthy
            rollback.container_running_after = health_check.container_running
            rollback.health_check_results = [{
                'status': health_check.status.value,
                'is_healthy': health_check.is_healthy,
                'failure_reason': health_check.failure_reason
            }]

            if not health_check.is_healthy:
                logger.warning("Health check failed after rollback")
                rollback.warnings.append("Health check failed after rollback")

            rollback.progress_percent = 100
            await session.commit()

            # STEP 8: Complete rollback
            logger.info("Step 8: Completing rollback")
            rollback.status = "completed"
            rollback.successful = True
            rollback.completed_at = datetime.utcnow()
            rollback.duration_seconds = int((rollback.completed_at - rollback.started_at).total_seconds())

            # Update update record
            update.status = UpdateStatus.ROLLED_BACK

            await session.commit()

            logger.info(f"Rollback completed successfully in {rollback.duration_seconds}s")
            return True, "Rollback completed successfully"

        except Exception as e:
            logger.error(f"Rollback error: {str(e)}")

            if rollback:
                rollback.status = "failed"
                rollback.error_message = str(e)
                rollback.successful = False
                await session.commit()

            return False, str(e)

    async def can_rollback(
        self,
        update_id: str,
        session: AsyncSession
    ) -> Tuple[bool, str]:
        """Check if update can be rolled back"""
        try:
            result = await session.execute(
                select(Update).where(Update.id == update_id)
            )
            update = result.scalar_one_or_none()

            if not update:
                return False, "Update not found"

            if not update.rollback_available:
                return False, "Rollback not available for this update"

            if update.status == UpdateStatus.ROLLED_BACK:
                return False, "Update already rolled back"

            if update.status == UpdateStatus.PENDING:
                return False, "Update not yet executed"

            # Check if previous config exists
            if not update.previous_container_config and not update.backup_path:
                return False, "No previous configuration or backup available"

            return True, "Rollback available"

        except Exception as e:
            logger.error(f"Error checking rollback availability: {str(e)}")
            return False, str(e)

    def _format_volumes(self, volumes: list) -> dict:
        """Format volumes for Docker SDK"""
        if not volumes:
            return {}

        result = {}
        for vol in volumes:
            if isinstance(vol, dict):
                host_path = vol.get('host_path')
                container_path = vol.get('container_path')
                mode = vol.get('mode', 'rw')
                if host_path and container_path:
                    result[host_path] = {'bind': container_path, 'mode': mode}

        return result

    def _format_ports(self, ports: list) -> dict:
        """Format ports for Docker SDK"""
        if not ports:
            return {}

        result = {}
        for port in ports:
            if isinstance(port, dict):
                container_port = port.get('container_port')
                host_port = port.get('host_port')
                if container_port and host_port:
                    result[container_port] = host_port

        return result


# Global instance
rollback_service = RollbackService()
