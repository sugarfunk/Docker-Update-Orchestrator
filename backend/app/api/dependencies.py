from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
from ..core.database import get_db
from ..models import ServiceDependency, Container
from ..services.dependency_service import dependency_service

router = APIRouter()


@router.post("/analyze")
async def analyze_dependencies(
    server_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Trigger dependency analysis"""
    try:
        count = await dependency_service.analyze_all_dependencies(db, server_id=server_id)

        return {
            "success": True,
            "dependencies_found": count,
            "message": f"Found {count} dependencies"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/container/{container_id}")
async def get_container_dependencies(
    container_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get dependencies for a container"""
    # Get outgoing dependencies (what this container depends on)
    outgoing = await db.execute(
        select(ServiceDependency).where(
            ServiceDependency.from_container_id == container_id
        )
    )
    outgoing_deps = outgoing.scalars().all()

    # Get incoming dependencies (what depends on this container)
    incoming = await db.execute(
        select(ServiceDependency).where(
            ServiceDependency.to_container_id == container_id
        )
    )
    incoming_deps = incoming.scalars().all()

    # Get container names
    async def get_container_name(cid: str) -> str:
        result = await db.execute(
            select(Container.container_name).where(Container.id == cid)
        )
        name = result.scalar_one_or_none()
        return name or "Unknown"

    outgoing_list = []
    for dep in outgoing_deps:
        outgoing_list.append({
            "id": dep.id,
            "to_container_id": dep.to_container_id,
            "to_container_name": await get_container_name(dep.to_container_id),
            "type": dep.dependency_type.value,
            "is_critical": dep.is_critical,
            "confidence": dep.confidence_score,
            "description": dep.description
        })

    incoming_list = []
    for dep in incoming_deps:
        incoming_list.append({
            "id": dep.id,
            "from_container_id": dep.from_container_id,
            "from_container_name": await get_container_name(dep.from_container_id),
            "type": dep.dependency_type.value,
            "is_critical": dep.is_critical,
            "confidence": dep.confidence_score,
            "description": dep.description
        })

    return {
        "outgoing": outgoing_list,  # What this depends on
        "incoming": incoming_list,  # What depends on this
        "total_outgoing": len(outgoing_list),
        "total_incoming": len(incoming_list)
    }


@router.get("/graph")
async def get_dependency_graph(
    server_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Get dependency graph for visualization"""
    graph = await dependency_service.get_dependency_graph(db, server_id=server_id)

    return graph


@router.get("/update-order")
async def get_update_order(
    container_ids: List[str],
    db: AsyncSession = Depends(get_db)
):
    """Get recommended update order for multiple containers"""
    order = await dependency_service.get_update_order(db, container_ids)

    # Convert to readable format
    result = []
    for level_idx, level in enumerate(order):
        container_names = []
        for cid in level:
            result_query = await db.execute(
                select(Container.container_name).where(Container.id == cid)
            )
            name = result_query.scalar_one_or_none()
            if name:
                container_names.append({
                    "id": cid,
                    "name": name
                })

        result.append({
            "level": level_idx + 1,
            "containers": container_names,
            "can_update_in_parallel": True
        })

    return {
        "update_order": result,
        "total_levels": len(result),
        "message": "Containers in the same level can be updated in parallel"
    }
