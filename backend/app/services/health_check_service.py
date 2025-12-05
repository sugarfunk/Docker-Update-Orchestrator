import httpx
import asyncio
import socket
import re
from typing import Optional, Dict, List
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Container, Server, HealthCheck, HealthStatus, ServiceConfig
from .docker_service import docker_service

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Service for running comprehensive health checks on containers"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def run_health_check(
        self,
        container: Container,
        server: Server,
        update_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> HealthCheck:
        """Run comprehensive health check on a container"""
        health_check = HealthCheck(
            container_id=container.id,
            update_id=update_id,
            check_started_at=datetime.utcnow(),
            status=HealthStatus.UNKNOWN,
            is_healthy=False
        )

        try:
            logger.info(f"Running health check for {container.container_name}")

            # Determine health check type
            if container.config and container.config.health_check_enabled:
                check_type = container.config.health_check_type
            else:
                check_type = self._auto_detect_health_check_type(container)

            health_check.check_type = check_type

            # Run appropriate health check
            if check_type == "http":
                await self._check_http(container, server, health_check)
            elif check_type == "tcp":
                await self._check_tcp(container, server, health_check)
            elif check_type == "custom":
                await self._check_custom_script(container, server, health_check)
            else:  # docker (default)
                await self._check_docker(container, server, health_check)

            # Check container resources
            await self._check_resources(container, server, health_check)

            # Check container logs for errors
            await self._check_logs(container, server, health_check)

            # Determine overall health
            health_check.is_healthy = self._determine_overall_health(health_check)
            health_check.status = HealthStatus.HEALTHY if health_check.is_healthy else HealthStatus.UNHEALTHY
            health_check.passed = health_check.is_healthy

            health_check.check_completed_at = datetime.utcnow()
            health_check.duration_seconds = int(
                (health_check.check_completed_at - health_check.check_started_at).total_seconds()
            )

            if session:
                session.add(health_check)
                await session.commit()

            logger.info(f"Health check completed: {health_check.status.value}")

            return health_check

        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            health_check.status = HealthStatus.UNHEALTHY
            health_check.is_healthy = False
            health_check.passed = False
            health_check.failure_reason = str(e)

            if session:
                session.add(health_check)
                await session.commit()

            return health_check

    async def _check_http(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Perform HTTP health check"""
        try:
            # Determine URL
            if container.config and container.config.health_check_url:
                url = container.config.health_check_url
            else:
                # Try to construct URL from container ports
                url = self._construct_health_url(container, server)

            if not url:
                health_check.failure_reason = "No HTTP endpoint configured"
                return

            health_check.http_url = url
            health_check.http_method = container.config.health_check_method if container.config else "GET"

            # Make HTTP request
            start_time = datetime.utcnow()

            if health_check.http_method == "GET":
                response = await self.http_client.get(url)
            elif health_check.http_method == "POST":
                response = await self.http_client.post(url)
            else:
                response = await self.http_client.get(url)

            end_time = datetime.utcnow()

            health_check.http_response_status = response.status_code
            health_check.http_response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            health_check.http_response_body = response.text[:1000]  # First 1000 chars

            # Check expected status
            expected_status = container.config.health_check_expected_status if container.config else 200

            if response.status_code == expected_status:
                logger.info(f"HTTP check passed: {url} returned {response.status_code}")
            else:
                health_check.failure_reason = f"HTTP status {response.status_code}, expected {expected_status}"
                logger.warning(health_check.failure_reason)

        except Exception as e:
            health_check.failure_reason = f"HTTP check failed: {str(e)}"
            logger.error(health_check.failure_reason)

    async def _check_tcp(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Perform TCP port check"""
        try:
            # Determine host and port
            if container.config and container.config.health_check_port:
                port = container.config.health_check_port
            else:
                # Use first exposed port
                if container.ports:
                    port = container.ports[0].get('host_port') if isinstance(container.ports[0], dict) else None
                else:
                    health_check.failure_reason = "No TCP port configured"
                    return

            health_check.tcp_host = server.hostname
            health_check.tcp_port = port

            # Try to connect
            start_time = datetime.utcnow()

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)

            try:
                result = sock.connect_ex((server.hostname, port))
                health_check.tcp_connected = (result == 0)

                end_time = datetime.utcnow()
                health_check.tcp_response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                if health_check.tcp_connected:
                    logger.info(f"TCP check passed: {server.hostname}:{port}")
                else:
                    health_check.failure_reason = f"Cannot connect to {server.hostname}:{port}"
                    logger.warning(health_check.failure_reason)

            finally:
                sock.close()

        except Exception as e:
            health_check.failure_reason = f"TCP check failed: {str(e)}"
            logger.error(health_check.failure_reason)

    async def _check_docker(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Check Docker container status"""
        try:
            containers = docker_service.list_containers(server.hostname, all_containers=True)

            for c in containers:
                if c['container_id'] == container.container_id:
                    health_check.container_state = c['state']
                    health_check.container_running = c['is_running']
                    health_check.docker_health_status = c.get('health', {}).get('Status')

                    if c['is_running']:
                        logger.info(f"Docker check passed: container is running")
                    else:
                        health_check.failure_reason = f"Container is not running (state: {c['state']})"
                        logger.warning(health_check.failure_reason)

                    # Check exit code if container exited
                    if c['state'] == 'exited':
                        health_check.exit_code = c.get('exit_code', -1)

                    return

            health_check.failure_reason = "Container not found"
            logger.error(health_check.failure_reason)

        except Exception as e:
            health_check.failure_reason = f"Docker check failed: {str(e)}"
            logger.error(health_check.failure_reason)

    async def _check_custom_script(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Run custom health check script"""
        try:
            if not container.config or not container.config.custom_health_check_script:
                health_check.failure_reason = "No custom script configured"
                return

            script = container.config.custom_health_check_script
            health_check.custom_script = script

            # Execute script via SSH
            # This would require SSH command execution
            # For now, just log it
            logger.info(f"Custom script health check: {script}")

            # TODO: Implement script execution
            health_check.failure_reason = "Custom scripts not yet implemented"

        except Exception as e:
            health_check.failure_reason = f"Custom script failed: {str(e)}"
            logger.error(health_check.failure_reason)

    async def _check_resources(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Check container resource usage"""
        try:
            containers = docker_service.list_containers(server.hostname)

            for c in containers:
                if c['container_id'] == container.container_id:
                    stats = c.get('stats', {})

                    if stats:
                        health_check.cpu_percent = int(stats.get('cpu_percent', 0))
                        health_check.memory_usage_mb = int(stats.get('memory_usage_mb', 0))
                        health_check.memory_percent = int(stats.get('memory_percent', 0))

                        # Check thresholds
                        cpu_threshold = container.config.cpu_threshold_percent if container.config else 90
                        memory_threshold = container.config.memory_threshold_percent if container.config else 90

                        if health_check.cpu_percent > cpu_threshold:
                            health_check.cpu_threshold_exceeded = True
                            logger.warning(f"CPU usage high: {health_check.cpu_percent}%")

                        if health_check.memory_percent > memory_threshold:
                            health_check.memory_threshold_exceeded = True
                            logger.warning(f"Memory usage high: {health_check.memory_percent}%")

                    return

        except Exception as e:
            logger.error(f"Resource check error: {str(e)}")

    async def _check_logs(
        self,
        container: Container,
        server: Server,
        health_check: HealthCheck
    ):
        """Check container logs for errors"""
        try:
            logs = docker_service.get_container_logs(
                server.hostname,
                container.container_id,
                tail=100
            )

            if logs:
                # Count error patterns
                error_patterns = [
                    r'error', r'ERROR', r'Error',
                    r'exception', r'Exception', r'EXCEPTION',
                    r'failed', r'FAILED', r'Failed',
                    r'fatal', r'FATAL', r'Fatal'
                ]

                critical_errors = []
                error_count = 0
                warning_count = 0

                for line in logs.split('\n'):
                    line_lower = line.lower()

                    if any(re.search(pattern, line, re.IGNORECASE) for pattern in error_patterns):
                        error_count += 1
                        if 'fatal' in line_lower or 'critical' in line_lower:
                            critical_errors.append(line[:200])

                    if 'warning' in line_lower or 'warn' in line_lower:
                        warning_count += 1

                health_check.error_count = error_count
                health_check.warning_count = warning_count
                health_check.critical_errors = critical_errors
                health_check.log_sample = logs[:1000]  # First 1000 chars

                if critical_errors:
                    logger.warning(f"Found {len(critical_errors)} critical errors in logs")

        except Exception as e:
            logger.error(f"Log check error: {str(e)}")

    def _determine_overall_health(self, health_check: HealthCheck) -> bool:
        """Determine overall health status"""
        # Container must be running
        if health_check.container_running is False:
            return False

        # If HTTP check was performed, it must pass
        if health_check.http_url:
            expected_status = 200
            if health_check.http_response_status != expected_status:
                return False

        # If TCP check was performed, it must pass
        if health_check.tcp_port:
            if not health_check.tcp_connected:
                return False

        # Check for critical errors in logs
        if health_check.critical_errors and len(health_check.critical_errors) > 0:
            return False

        # Check resource thresholds
        if health_check.cpu_threshold_exceeded or health_check.memory_threshold_exceeded:
            # Only fail if severely exceeded
            if health_check.cpu_percent and health_check.cpu_percent > 95:
                return False
            if health_check.memory_percent and health_check.memory_percent > 95:
                return False

        # If we got here, consider it healthy
        return True

    def _auto_detect_health_check_type(self, container: Container) -> str:
        """Auto-detect appropriate health check type"""
        # Check if container has HTTP ports
        if container.ports:
            for port in container.ports:
                if isinstance(port, dict):
                    container_port = str(port.get('container_port', ''))
                    # Common HTTP ports
                    if any(p in container_port for p in ['80', '443', '8080', '3000', '5000']):
                        return "http"

        # Check container labels for health check hints
        if container.labels:
            if 'health.check.type' in container.labels:
                return container.labels['health.check.type']

        # Default to docker check
        return "docker"

    def _construct_health_url(self, container: Container, server: Server) -> Optional[str]:
        """Construct health check URL from container info"""
        if not container.ports:
            return None

        # Find HTTP port
        http_port = None
        for port in container.ports:
            if isinstance(port, dict):
                container_port = str(port.get('container_port', ''))
                if any(p in container_port for p in ['80', '443', '8080', '3000', '5000', '8000']):
                    http_port = port.get('host_port')
                    break

        if not http_port:
            return None

        # Determine health path
        health_path = "/health"
        if container.labels and 'health.check.path' in container.labels:
            health_path = container.labels['health.check.path']

        # Construct URL
        protocol = "https" if http_port == 443 else "http"
        url = f"{protocol}://{server.hostname}:{http_port}{health_path}"

        return url

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# Global instance
health_check_service = HealthCheckService()
