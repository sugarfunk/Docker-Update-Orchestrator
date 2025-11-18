from sqlalchemy import Column, String, DateTime, JSON, Text, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class NotificationChannel(str, Enum):
    """Notification delivery channel"""
    NTFY = "ntfy"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"


class NotificationPriority(str, Enum):
    """Notification priority level"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Notification(Base):
    """Notification model"""

    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Notification Content
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    priority = Column(SQLEnum(NotificationPriority), nullable=False, default=NotificationPriority.NORMAL)

    # Related Entities
    container_id = Column(String, nullable=True, index=True)
    container_name = Column(String, nullable=True)
    server_name = Column(String, nullable=True)
    update_id = Column(String, nullable=True, index=True)
    rollback_id = Column(String, nullable=True)

    # Notification Type
    notification_type = Column(String, nullable=False, index=True)
    # Types: update_available, breaking_change_detected, update_started, update_completed,
    #        update_failed, health_check_failed, rollback_executed, approval_required, etc.

    # Delivery
    channels = Column(JSON, default=list)  # List of NotificationChannel values
    sent_to = Column(JSON, default=dict)  # {channel: [recipients]}
    delivery_status = Column(JSON, default=dict)  # {channel: status}

    # Status
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed = Column(Boolean, default=False)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Action Buttons (for interactive notifications)
    actions = Column(JSON, default=list)
    # Example: [{"label": "Approve", "action": "approve_update", "url": "..."}]
    action_taken = Column(String, nullable=True)
    action_taken_by = Column(String, nullable=True)
    action_taken_at = Column(DateTime(timezone=True), nullable=True)

    # Links
    dashboard_url = Column(String, nullable=True)
    details_url = Column(String, nullable=True)

    # NTFY Specific
    ntfy_tags = Column(JSON, default=list)  # ["warning", "update", etc]
    ntfy_click_url = Column(String, nullable=True)
    ntfy_attach_url = Column(String, nullable=True)

    # Email Specific
    email_recipients = Column(JSON, default=list)
    email_html = Column(Text, nullable=True)
    email_sent_ids = Column(JSON, default=list)

    # Webhook Specific
    webhook_urls = Column(JSON, default=list)
    webhook_responses = Column(JSON, default=list)

    # Grouping (for digest notifications)
    digest_group = Column(String, nullable=True)
    is_digest = Column(Boolean, default=False)
    digest_count = Column(Integer, default=1)

    # Metadata
    metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Notification {self.title} ({self.notification_type})>"


from sqlalchemy import Integer
