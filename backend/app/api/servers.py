from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from ..core.database import get_db
from ..models import Server
from ..services.docker_service import docker_service

router = APIRouter()


class ServerCreate(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str = "root"
    ssh_key_path: str | None = None
    tailscale_ip: str | None = None
    local_ip: str | None = None
    tags: List[str] = []
    notes: str | None = None


class ServerResponse(BaseModel):
    id: str
    name: str
    hostname: str
    port: int
    is_active: bool
    connection_status: str
    docker_version: str | None
    os_type: str | None
    os_version: str | None
    containers_count: int = 0

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ServerResponse])
async def list_servers(db: AsyncSession = Depends(get_db)):
    """List all servers"""
    result = await db.execute(select(Server))
    servers = result.scalars().all()

    return [
        ServerResponse(
            id=server.id,
            name=server.name,
            hostname=server.hostname,
            port=server.port,
            is_active=server.is_active,
            connection_status=server.connection_status,
            docker_version=server.docker_version,
            os_type=server.os_type,
            os_version=server.os_version,
            containers_count=len(server.containers) if server.containers else 0
        )
        for server in servers
    ]


@router.post("/", response_model=ServerResponse)
async def create_server(server_data: ServerCreate, db: AsyncSession = Depends(get_db)):
    """Add a new server"""
    server = Server(
        name=server_data.name,
        hostname=server_data.hostname,
        port=server_data.port,
        username=server_data.username,
        ssh_key_path=server_data.ssh_key_path,
        tailscale_ip=server_data.tailscale_ip,
        local_ip=server_data.local_ip,
        tags=server_data.tags,
        notes=server_data.notes
    )

    db.add(server)
    await db.commit()
    await db.refresh(server)

    return ServerResponse(
        id=server.id,
        name=server.name,
        hostname=server.hostname,
        port=server.port,
        is_active=server.is_active,
        connection_status=server.connection_status,
        docker_version=server.docker_version,
        os_type=server.os_type,
        os_version=server.os_version
    )


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Get server details"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    return ServerResponse(
        id=server.id,
        name=server.name,
        hostname=server.hostname,
        port=server.port,
        is_active=server.is_active,
        connection_status=server.connection_status,
        docker_version=server.docker_version,
        os_type=server.os_type,
        os_version=server.os_version,
        containers_count=len(server.containers) if server.containers else 0
    )


@router.post("/{server_id}/connect")
async def connect_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Connect to a server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Try to connect
    success, message = docker_service.connect_to_server(
        hostname=server.hostname,
        port=server.port,
        username=server.username,
        ssh_key_path=server.ssh_key_path
    )

    # Update server status
    server.connection_status = "connected" if success else "error"
    server.is_active = success

    if success:
        # Get server info
        server_info = docker_service.get_server_info(server.hostname)
        if server_info:
            server.docker_version = server_info["docker_version"]
            server.os_type = server_info["os_type"]
            server.os_version = server_info["os_version"]
            server.architecture = server_info["architecture"]
            server.cpu_count = server_info["cpu_count"]
            server.memory_total_mb = server_info["memory_total_mb"]

    await db.commit()

    return {
        "success": success,
        "message": message,
        "server_id": server_id
    }


@router.post("/{server_id}/disconnect")
async def disconnect_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Disconnect from a server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    docker_service.disconnect_from_server(server.hostname)
    server.connection_status = "disconnected"

    await db.commit()

    return {"success": True, "message": "Disconnected"}


@router.delete("/{server_id}")
async def delete_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Disconnect if connected
    docker_service.disconnect_from_server(server.hostname)

    await db.delete(server)
    await db.commit()

    return {"success": True, "message": "Server deleted"}
