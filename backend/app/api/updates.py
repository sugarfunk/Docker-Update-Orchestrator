from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_db
from ..models import Update, UpdateStatus, Container, Server

router = APIRouter()


class UpdateResponse(BaseModel):
    id: str
    container_name: str
    server_name: str
    from_version: str
    to_version: str
    update_type: str
    status: str
    risk_level: str | None
    has_breaking_changes: bool
    safe_to_auto_update: bool
    created_at: str

    class Config:
        from_attributes = True


class UpdateDetailResponse(UpdateResponse):
    changelog_summary: str | None
    breaking_changes: list
    config_changes_required: list
    action_items: list
    risk_factors: list
    requires_downtime: bool
    estimated_downtime_seconds: int | None
    health_checks_passed: bool | None
    error_message: str | None

    class Config:
        from_attributes = True


class UpdateApproval(BaseModel):
    approved: bool
    notes: str | None = None


@router.get("/", response_model=List[UpdateResponse])
async def list_updates(
    status: Optional[str] = Query(None),
    container_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """List updates with optional filters"""
    query = select(Update).order_by(desc(Update.created_at))

    if status:
        query = query.where(Update.status == status)
    if container_id:
        query = query.where(Update.container_id == container_id)

    query = query.limit(limit)

    result = await db.execute(query)
    updates = result.scalars().all()

    response = []
    for update in updates:
        # Get container and server info
        container_result = await db.execute(
            select(Container).where(Container.id == update.container_id)
        )
        container = container_result.scalar_one_or_none()

        if container:
            server_result = await db.execute(
                select(Server.name).where(Server.id == container.server_id)
            )
            server_name = server_result.scalar_one_or_none() or "Unknown"
            container_name = container.container_name
        else:
            server_name = "Unknown"
            container_name = "Unknown"

        response.append(UpdateResponse(
            id=update.id,
            container_name=container_name,
            server_name=server_name,
            from_version=update.from_version,
            to_version=update.to_version,
            update_type=update.update_type.value,
            status=update.status.value,
            risk_level=update.risk_level,
            has_breaking_changes=len(update.breaking_changes) > 0 if update.breaking_changes else False,
            safe_to_auto_update=update.safe_to_auto_update,
            created_at=update.created_at.isoformat() if update.created_at else datetime.utcnow().isoformat()
        ))

    return response


@router.get("/{update_id}", response_model=UpdateDetailResponse)
async def get_update(update_id: str, db: AsyncSession = Depends(get_db)):
    """Get update details"""
    result = await db.execute(select(Update).where(Update.id == update_id))
    update = result.scalar_one_or_none()

    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    # Get container and server info
    container_result = await db.execute(
        select(Container).where(Container.id == update.container_id)
    )
    container = container_result.scalar_one_or_none()

    if container:
        server_result = await db.execute(
            select(Server.name).where(Server.id == container.server_id)
        )
        server_name = server_result.scalar_one_or_none() or "Unknown"
        container_name = container.container_name
    else:
        server_name = "Unknown"
        container_name = "Unknown"

    return UpdateDetailResponse(
        id=update.id,
        container_name=container_name,
        server_name=server_name,
        from_version=update.from_version,
        to_version=update.to_version,
        update_type=update.update_type.value,
        status=update.status.value,
        risk_level=update.risk_level,
        has_breaking_changes=len(update.breaking_changes) > 0 if update.breaking_changes else False,
        safe_to_auto_update=update.safe_to_auto_update,
        created_at=update.created_at.isoformat() if update.created_at else datetime.utcnow().isoformat(),
        changelog_summary=update.changelog_summary,
        breaking_changes=update.breaking_changes or [],
        config_changes_required=update.config_changes_required or [],
        action_items=update.action_items or [],
        risk_factors=update.risk_factors or [],
        requires_downtime=update.requires_downtime,
        estimated_downtime_seconds=update.estimated_downtime_seconds,
        health_checks_passed=update.health_checks_passed,
        error_message=update.error_message
    )


@router.post("/{update_id}/approve")
async def approve_update(
    update_id: str,
    approval: UpdateApproval,
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject an update"""
    result = await db.execute(select(Update).where(Update.id == update_id))
    update = result.scalar_one_or_none()

    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    if update.status != UpdateStatus.PENDING:
        raise HTTPException(status_code=400, detail="Update is not pending approval")

    if approval.approved:
        update.status = UpdateStatus.APPROVED
        update.approved_at = datetime.utcnow()
        update.approval_notes = approval.notes
        # TODO: Trigger Celery task to execute update
    else:
        update.status = UpdateStatus.SKIPPED
        update.approval_notes = approval.notes

    await db.commit()

    return {
        "success": True,
        "message": "Update approved" if approval.approved else "Update rejected",
        "update_id": update_id
    }


@router.post("/{update_id}/execute")
async def execute_update(update_id: str, db: AsyncSession = Depends(get_db)):
    """Execute an update"""
    result = await db.execute(select(Update).where(Update.id == update_id))
    update = result.scalar_one_or_none()

    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    if update.status not in [UpdateStatus.PENDING, UpdateStatus.APPROVED]:
        raise HTTPException(status_code=400, detail="Update cannot be executed in current status")

    # TODO: Trigger Celery task to execute update
    update.status = UpdateStatus.IN_PROGRESS
    update.started_at = datetime.utcnow()
    await db.commit()

    return {
        "success": True,
        "message": "Update execution started",
        "update_id": update_id
    }


@router.post("/{update_id}/rollback")
async def rollback_update(update_id: str, db: AsyncSession = Depends(get_db)):
    """Rollback an update"""
    result = await db.execute(select(Update).where(Update.id == update_id))
    update = result.scalar_one_or_none()

    if not update:
        raise HTTPException(status_code=404, detail="Update not found")

    if not update.rollback_available:
        raise HTTPException(status_code=400, detail="Rollback not available for this update")

    # TODO: Trigger Celery task to execute rollback

    return {
        "success": True,
        "message": "Rollback started",
        "update_id": update_id
    }


@router.get("/stats/summary")
async def get_update_stats(db: AsyncSession = Depends(get_db)):
    """Get update statistics"""
    pending_result = await db.execute(
        select(Update).where(Update.status == UpdateStatus.PENDING)
    )
    pending = len(pending_result.scalars().all())

    in_progress_result = await db.execute(
        select(Update).where(Update.status == UpdateStatus.IN_PROGRESS)
    )
    in_progress = len(in_progress_result.scalars().all())

    completed_result = await db.execute(
        select(Update).where(Update.status == UpdateStatus.COMPLETED)
    )
    completed = len(completed_result.scalars().all())

    failed_result = await db.execute(
        select(Update).where(Update.status == UpdateStatus.FAILED)
    )
    failed = len(failed_result.scalars().all())

    return {
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "failed": failed
    }
