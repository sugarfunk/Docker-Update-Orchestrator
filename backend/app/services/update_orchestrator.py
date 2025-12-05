import asyncio
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models import (
    Update, UpdateStatus, Container, Server, HealthCheck, HealthStatus,
    Rollback, RollbackReason
)
from .docker_service import docker_service
from .health_check_service import health_check_service
from .backup_service import backup_service
from .notification_service import notification_service

logger = logging.getLogger(__name__)


class UpdateOrchestrator:
    """Orchestrates the complete update process with health checks and rollback"""

    def __init__(self):
        self.max_retries = 3
        self.health_check_interval = 10  # seconds

    async def execute_update(
        self,
        update_id: str,
        session: AsyncSession
    ) -> Tuple[bool, str]:
        """Execute a complete update with all safety checks"""
        try:
            # Get update and related data
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

            # Update status
            update.status = UpdateStatus.IN_PROGRESS
            update.started_at = datetime.utcnow()
            update.current_step = "Starting update process"
            await session.commit()

            logger.info(f"Starting update: {container.container_name} {update.from_version} -> {update.to_version}")

            # STEP 1: Pre-update validation
            logger.info("Step 1: Pre-update validation")
            update.current_step = "Validating prerequisites"
            await session.commit()

            if not await self._validate_prerequisites(update, container, server, session):
                update.status = UpdateStatus.FAILED
                update.error_message = "Prerequisites validation failed"
                await session.commit()
                return False, "Prerequisites validation failed"

            # STEP 2: Create backup
            if update.backup_created or (container.config and container.config.backup_before_update):
                logger.info("Step 2: Creating backup")
                update.current_step = "Creating backup"
                await session.commit()

                backup_path = await backup_service.create_backup(
                    container=container,
                    server=server,
                    session=session
                )

                if backup_path:
                    update.backup_created = True
                    update.backup_path = backup_path
                    update.previous_container_config = {
                        'image': container.image,
                        'image_id': container.image_id,
                        'environment': container.environment_vars,
                        'volumes': container.volumes,
                        'networks': container.networks,
                        'ports': container.ports,
                        'command': container.command,
                        'entrypoint': container.entrypoint
                    }
                    await session.commit()
                    logger.info(f"Backup created: {backup_path}")
                else:
                    logger.warning("Backup creation failed, continuing anyway")

            # STEP 3: Pull new image
            logger.info("Step 3: Pulling new image")
            update.status = UpdateStatus.PULLING_IMAGE
            update.current_step = f"Pulling image {update.to_image}"
            await session.commit()

            success, message = docker_service.pull_image(server.hostname, update.to_image)

            if not success:
                update.status = UpdateStatus.FAILED
                update.error_message = f"Failed to pull image: {message}"
                await session.commit()
                logger.error(f"Image pull failed: {message}")
                return False, f"Failed to pull image: {message}"

            logger.info("Image pulled successfully")
            update.progress_percent = 33
            await session.commit()

            # STEP 4: Stop old container
            logger.info("Step 4: Stopping old container")
            update.status = UpdateStatus.STOPPING_CONTAINER
            update.current_step = "Stopping old container"
            await session.commit()

            success, message = docker_service.stop_container(
                server.hostname,
                container.container_id,
                timeout=30
            )

            if not success:
                update.status = UpdateStatus.FAILED
                update.error_message = f"Failed to stop container: {message}"
                await session.commit()
                logger.error(f"Container stop failed: {message}")
                return False, f"Failed to stop container: {message}"

            logger.info("Container stopped")
            update.progress_percent = 50
            await session.commit()

            # STEP 5: Remove old container
            logger.info("Step 5: Removing old container")
            update.current_step = "Removing old container"
            await session.commit()

            docker_service.remove_container(server.hostname, container.container_id)

            # STEP 6: Create new container
            logger.info("Step 6: Creating new container with new image")
            update.status = UpdateStatus.STARTING_CONTAINER
            update.current_step = "Creating new container"
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
                update.to_image,
                **container_config
            )

            if not success:
                update.status = UpdateStatus.FAILED
                update.error_message = f"Failed to create container: {message}"
                await session.commit()
                logger.error(f"Container creation failed: {message}")

                # Try to rollback
                await self._rollback_update(update, container, server, session, RollbackReason.CONTAINER_CRASHED)
                return False, f"Failed to create container: {message}"

            logger.info(f"New container created: {new_container_id}")
            update.progress_percent = 66
            await session.commit()

            # STEP 7: Start new container
            logger.info("Step 7: Starting new container")
            update.current_step = "Starting new container"
            await session.commit()

            success, message = docker_service.start_container(server.hostname, new_container_id)

            if not success:
                update.status = UpdateStatus.FAILED
                update.error_message = f"Failed to start container: {message}"
                await session.commit()
                logger.error(f"Container start failed: {message}")

                # Rollback
                await self._rollback_update(update, container, server, session, RollbackReason.CONTAINER_CRASHED)
                return False, f"Failed to start container: {message}"

            # Update container record
            container.container_id = new_container_id
            container.image = update.to_image
            container.tag = update.to_version
            await session.commit()

            logger.info("Container started successfully")
            update.progress_percent = 80
            await session.commit()

            # STEP 8: Health checks
            logger.info("Step 8: Running health checks")
            update.status = UpdateStatus.HEALTH_CHECKING
            update.current_step = "Running health checks"
            await session.commit()

            # Wait a bit for container to start
            await asyncio.sleep(10)

            health_passed = await self._run_health_checks(update, container, server, session)

            if not health_passed:
                logger.error("Health checks failed")
                update.status = UpdateStatus.FAILED
                update.error_message = "Health checks failed"
                update.health_checks_passed = False
                await session.commit()

                # Automatic rollback
                await self._rollback_update(update, container, server, session, RollbackReason.HEALTH_CHECK_FAILED)
                return False, "Health checks failed - rolled back to previous version"

            logger.info("Health checks passed")
            update.health_checks_passed = True
            update.progress_percent = 100
            await session.commit()

            # STEP 9: Complete
            logger.info("Step 9: Update completed")
            update.status = UpdateStatus.COMPLETED
            update.completed_at = datetime.utcnow()
            update.duration_seconds = int((update.completed_at - update.started_at).total_seconds())
            update.rollback_available = True
            container.last_updated = datetime.utcnow()
            container.update_available = False
            await session.commit()

            # Send notification
            await notification_service.send_update_completed(
                container_name=container.container_name,
                server_name=server.name,
                version=update.to_version,
                duration_seconds=update.duration_seconds
            )

            logger.info(f"Update completed successfully in {update.duration_seconds}s")
            return True, "Update completed successfully"

        except Exception as e:
            logger.error(f"Error executing update: {str(e)}")
            if update:
                update.status = UpdateStatus.FAILED
                update.error_message = str(e)
                await session.commit()

            return False, str(e)

    async def _validate_prerequisites(
        self,
        update: Update,
        container: Container,
        server: Server,
        session: AsyncSession
    ) -> bool:
        """Validate prerequisites before update"""
        try:
            # Check if server is connected
            if server.connection_status != "connected":
                success, _ = docker_service.connect_to_server(
                    server.hostname,
                    server.port,
                    server.username,
                    server.ssh_key_path
                )
                if not success:
                    logger.error(f"Cannot connect to server {server.name}")
                    return False

            # Check if container is running (if required)
            containers = docker_service.list_containers(server.hostname)
            container_found = False

            for c in containers:
                if c['container_id'] == container.container_id:
                    container_found = True
                    break

            if not container_found:
                logger.error(f"Container {container.container_name} not found on server")
                return False

            return True

        except Exception as e:
            logger.error(f"Prerequisites validation error: {str(e)}")
            return False

    async def _run_health_checks(
        self,
        update: Update,
        container: Container,
        server: Server,
        session: AsyncSession
    ) -> bool:
        """Run health checks on updated container"""
        max_attempts = 3
        wait_between_checks = 10

        for attempt in range(max_attempts):
            logger.info(f"Health check attempt {attempt + 1}/{max_attempts}")

            # Wait before checking
            if attempt > 0:
                await asyncio.sleep(wait_between_checks)

            # Run health check
            health_check = await health_check_service.run_health_check(
                container=container,
                server=server,
                update_id=update.id,
                session=session
            )

            update.health_check_count += 1

            if health_check.is_healthy:
                logger.info("Health check passed")
                return True
            else:
                logger.warning(f"Health check failed: {health_check.failure_reason}")
                update.health_check_failures += 1

        logger.error("All health checks failed")
        return False

    async def _rollback_update(
        self,
        update: Update,
        container: Container,
        server: Server,
        session: AsyncSession,
        reason: RollbackReason
    ) -> bool:
        """Rollback to previous version"""
        logger.info(f"Starting rollback due to: {reason.value}")

        try:
            # Create rollback record
            from ..services.rollback_service import rollback_service

            success, message = await rollback_service.execute_rollback(
                update_id=update.id,
                reason=reason,
                session=session
            )

            if success:
                update.status = UpdateStatus.ROLLED_BACK
                await session.commit()
                logger.info("Rollback completed successfully")

                # Send notification
                await notification_service.send_rollback_executed(
                    container_name=container.container_name,
                    server_name=server.name,
                    from_version=update.to_version,
                    to_version=update.from_version,
                    reason=reason.value
                )

            return success

        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            return False

    def _format_volumes(self, volumes: List) -> Dict:
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

    def _format_ports(self, ports: List) -> Dict:
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
update_orchestrator = UpdateOrchestrator()
