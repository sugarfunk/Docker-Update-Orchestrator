from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from pydantic import BaseModel
from ..core.database import get_db
from ..models import Notification

router = APIRouter()


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    priority: str
    notification_type: str
    sent: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("/", response_model=List[NotificationResponse])
async def list_notifications(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List recent notifications"""
    result = await db.execute(
        select(Notification)
        .order_by(desc(Notification.created_at))
        .limit(limit)
    )
    notifications = result.scalars().all()

    return [
        NotificationResponse(
            id=notif.id,
            title=notif.title,
            message=notif.message,
            priority=notif.priority.value,
            notification_type=notif.notification_type,
            sent=notif.sent,
            created_at=notif.created_at.isoformat() if notif.created_at else ""
        )
        for notif in notifications
    ]
