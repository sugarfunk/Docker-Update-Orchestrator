from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from ..core.database import get_db
from ..models import Rollback, RollbackReason
from ..services.rollback_service import rollback_service

router = APIRouter()


class RollbackRequest(BaseModel):
    reason: str = "manual"
    notes: str | None = None


class RollbackResponse(BaseModel):
    id: str
    update_id: str
    reason: str
    status: str
    successful: bool
    rolled_back_from: str
    rolled_back_to: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/{update_id}")
async def execute_rollback(
    update_id: str,
    rollback_request: RollbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute a rollback for an update"""
    # Validate reason
    try:
        reason = RollbackReason(rollback_request.reason)
    except ValueError:
        reason = RollbackReason.MANUAL

    # Check if rollback is possible
    can_rollback, message = await rollback_service.can_rollback(update_id, db)

    if not can_rollback:
        raise HTTPException(status_code=400, detail=message)

    # Execute rollback
    success, message = await rollback_service.execute_rollback(
        update_id=update_id,
        reason=reason,
        session=db,
        triggered_by="user"
    )

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {
        "success": True,
        "message": message,
        "update_id": update_id
    }


@router.get("/{update_id}", response_model=RollbackResponse)
async def get_rollback(update_id: str, db: AsyncSession = Depends(get_db)):
    """Get rollback details for an update"""
    result = await db.execute(
        select(Rollback).where(Rollback.update_id == update_id)
    )
    rollback = result.scalar_one_or_none()

    if not rollback:
        raise HTTPException(status_code=404, detail="Rollback not found")

    return RollbackResponse(
        id=rollback.id,
        update_id=rollback.update_id,
        reason=rollback.reason.value,
        status=rollback.status,
        successful=rollback.successful,
        rolled_back_from=rollback.rolled_back_from,
        rolled_back_to=rollback.rolled_back_to,
        created_at=rollback.created_at.isoformat() if rollback.created_at else ""
    )


@router.get("/{update_id}/can-rollback")
async def can_rollback_check(update_id: str, db: AsyncSession = Depends(get_db)):
    """Check if an update can be rolled back"""
    can_rollback, message = await rollback_service.can_rollback(update_id, db)

    return {
        "can_rollback": can_rollback,
        "message": message,
        "update_id": update_id
    }


@router.get("/", response_model=List[RollbackResponse])
async def list_rollbacks(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """List recent rollbacks"""
    result = await db.execute(
        select(Rollback)
        .order_by(Rollback.created_at.desc())
        .limit(limit)
    )
    rollbacks = result.scalars().all()

    return [
        RollbackResponse(
            id=r.id,
            update_id=r.update_id,
            reason=r.reason.value,
            status=r.status,
            successful=r.successful,
            rolled_back_from=r.rolled_back_from,
            rolled_back_to=r.rolled_back_to,
            created_at=r.created_at.isoformat() if r.created_at else ""
        )
        for r in rollbacks
    ]
