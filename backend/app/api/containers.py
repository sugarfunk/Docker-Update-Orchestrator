from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from ..core.database import get_db
from ..models import Container, Server

router = APIRouter()


class ContainerResponse(BaseModel):
    id: str
    container_id: str
    container_name: str
    image: str
    tag: str | None
    status: str
    is_running: bool
    server_name: str
    update_available: bool
    latest_version: str | None
    is_critical: bool
    auto_update_enabled: bool
    health_status: str | None

    class Config:
        from_attributes = True


class ContainerDetailResponse(ContainerResponse):
    registry: str | None
    repository: str | None
    digest: str | None
    environment_vars: list
    volumes: list
    networks: list
    ports: list
    labels: dict
    created_at: str | None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ContainerResponse])
async def list_containers(
    server_id: Optional[str] = Query(None),
    update_available: Optional[bool] = Query(None),
    is_critical: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List all containers with optional filters"""
    query = select(Container)

    if server_id:
        query = query.where(Container.server_id == server_id)
    if update_available is not None:
        query = query.where(Container.update_available == update_available)
    if is_critical is not None:
        query = query.where(Container.is_critical == is_critical)

    result = await db.execute(query)
    containers = result.scalars().all()

    response = []
    for container in containers:
        # Get server name
        server_result = await db.execute(
            select(Server.name).where(Server.id == container.server_id)
        )
        server_name = server_result.scalar_one_or_none() or "Unknown"

        response.append(ContainerResponse(
            id=container.id,
            container_id=container.container_id,
            container_name=container.container_name,
            image=container.image,
            tag=container.tag,
            status=container.status,
            is_running=container.is_running,
            server_name=server_name,
            update_available=container.update_available,
            latest_version=container.latest_version,
            is_critical=container.is_critical,
            auto_update_enabled=container.auto_update_enabled,
            health_status=container.health_status
        ))

    return response


@router.get("/{container_id}", response_model=ContainerDetailResponse)
async def get_container(container_id: str, db: AsyncSession = Depends(get_db)):
    """Get container details"""
    result = await db.execute(select(Container).where(Container.id == container_id))
    container = result.scalar_one_or_none()

    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    # Get server name
    server_result = await db.execute(
        select(Server.name).where(Server.id == container.server_id)
    )
    server_name = server_result.scalar_one_or_none() or "Unknown"

    return ContainerDetailResponse(
        id=container.id,
        container_id=container.container_id,
        container_name=container.container_name,
        image=container.image,
        tag=container.tag,
        registry=container.registry,
        repository=container.repository,
        digest=container.digest,
        status=container.status,
        is_running=container.is_running,
        server_name=server_name,
        update_available=container.update_available,
        latest_version=container.latest_version,
        is_critical=container.is_critical,
        auto_update_enabled=container.auto_update_enabled,
        health_status=container.health_status,
        environment_vars=container.environment_vars or [],
        volumes=container.volumes or [],
        networks=container.networks or [],
        ports=container.ports or [],
        labels=container.labels or {},
        created_at=container.created_at.isoformat() if container.created_at else None
    )


@router.post("/{container_id}/scan")
async def scan_container(container_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger update check for a container"""
    result = await db.execute(select(Container).where(Container.id == container_id))
    container = result.scalar_one_or_none()

    if not container:
        raise HTTPException(status_code=404, detail="Container not found")

    # TODO: Trigger Celery task to check for updates
    # For now, return a placeholder response

    return {
        "success": True,
        "message": "Update check queued",
        "container_id": container_id
    }


@router.get("/stats/summary")
async def get_container_stats(db: AsyncSession = Depends(get_db)):
    """Get container statistics summary"""
    total_result = await db.execute(select(Container))
    total = len(total_result.scalars().all())

    running_result = await db.execute(
        select(Container).where(Container.is_running == True)
    )
    running = len(running_result.scalars().all())

    updates_result = await db.execute(
        select(Container).where(Container.update_available == True)
    )
    updates_available = len(updates_result.scalars().all())

    critical_result = await db.execute(
        select(Container).where(Container.is_critical == True)
    )
    critical = len(critical_result.scalars().all())

    return {
        "total_containers": total,
        "running_containers": running,
        "updates_available": updates_available,
        "critical_services": critical
    }
