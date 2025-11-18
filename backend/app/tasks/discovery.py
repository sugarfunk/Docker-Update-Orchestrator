from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..core.config import settings
from ..models import Server, Container
from ..services.docker_service import docker_service
import logging
import asyncio

logger = logging.getLogger(__name__)

# Create async database session for tasks
engine = create_async_engine(settings.DATABASE_URL)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.discovery.scan_all_servers")
def scan_all_servers():
    """Scan all servers and discover containers"""
    asyncio.run(_scan_all_servers_async())


async def _scan_all_servers_async():
    """Async implementation of scan_all_servers"""
    async with async_session_maker() as session:
        try:
            # Get all active servers
            result = await session.execute(
                select(Server).where(Server.is_active == True)
            )
            servers = result.scalars().all()

            logger.info(f"Scanning {len(servers)} servers for containers")

            for server in servers:
                try:
                    await _scan_server(server, session)
                except Exception as e:
                    logger.error(f"Error scanning server {server.name}: {str(e)}")

            await session.commit()
            logger.info("Server scan completed")

        except Exception as e:
            logger.error(f"Error in scan_all_servers: {str(e)}")
            await session.rollback()


async def _scan_server(server: Server, session: AsyncSession):
    """Scan a single server for containers"""
    logger.info(f"Scanning server: {server.name}")

    # Connect to server
    success, message = docker_service.connect_to_server(
        hostname=server.hostname,
        port=server.port,
        username=server.username,
        ssh_key_path=server.ssh_key_path
    )

    if not success:
        logger.error(f"Failed to connect to {server.name}: {message}")
        server.connection_status = "error"
        return

    server.connection_status = "connected"

    # Get server info
    server_info = docker_service.get_server_info(server.hostname)
    if server_info:
        server.docker_version = server_info["docker_version"]
        server.os_type = server_info["os_type"]
        server.os_version = server_info["os_version"]
        server.architecture = server_info["architecture"]
        server.cpu_count = server_info["cpu_count"]
        server.memory_total_mb = server_info["memory_total_mb"]

    # List containers
    containers_data = docker_service.list_containers(server.hostname)

    logger.info(f"Found {len(containers_data)} containers on {server.name}")

    # Update database
    for container_data in containers_data:
        # Check if container already exists
        result = await session.execute(
            select(Container).where(
                Container.server_id == server.id,
                Container.container_id == container_data["container_id"]
            )
        )
        container = result.scalar_one_or_none()

        if container:
            # Update existing container
            container.container_name = container_data["name"]
            container.image = container_data["image"]
            container.status = container_data["status"]
            container.is_running = container_data["is_running"]
            container.tag = container_data["tag"]
            container.registry = container_data["registry"]
            container.repository = container_data["repository"]
            container.environment_vars = container_data.get("environment", [])
            container.volumes = container_data.get("volumes", [])
            container.networks = container_data.get("networks", [])
            container.ports = container_data.get("ports", [])
            container.labels = container_data.get("labels", {})
        else:
            # Create new container
            container = Container(
                server_id=server.id,
                container_id=container_data["container_id"],
                container_name=container_data["name"],
                image=container_data["image"],
                image_id=container_data["image_id"],
                registry=container_data["registry"],
                repository=container_data["repository"],
                tag=container_data["tag"],
                status=container_data["status"],
                state=container_data["state"],
                is_running=container_data["is_running"],
                environment_vars=container_data.get("environment", []),
                volumes=container_data.get("volumes", []),
                networks=container_data.get("networks", []),
                ports=container_data.get("ports", []),
                labels=container_data.get("labels", {}),
                command=str(container_data.get("command")),
                entrypoint=str(container_data.get("entrypoint"))
            )
            session.add(container)

    logger.info(f"Completed scanning {server.name}")


@shared_task(name="app.tasks.discovery.scan_server")
def scan_server(server_id: str):
    """Scan a specific server"""
    asyncio.run(_scan_server_by_id(server_id))


async def _scan_server_by_id(server_id: str):
    """Async implementation of scan_server"""
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(Server).where(Server.id == server_id)
            )
            server = result.scalar_one_or_none()

            if not server:
                logger.error(f"Server {server_id} not found")
                return

            await _scan_server(server, session)
            await session.commit()

        except Exception as e:
            logger.error(f"Error scanning server {server_id}: {str(e)}")
            await session.rollback()
