from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class RollbackReason(str, Enum):
    """Reason for rollback"""
    HEALTH_CHECK_FAILED = "health_check_failed"
    CONTAINER_CRASHED = "container_crashed"
    HIGH_ERROR_RATE = "high_error_rate"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    OTHER = "other"


class Rollback(Base):
    """Rollback execution model"""

    __tablename__ = "rollbacks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    update_id = Column(String, ForeignKey("updates.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Rollback Info
    reason = Column(SQLEnum(RollbackReason), nullable=False)
    reason_details = Column(Text, nullable=True)
    triggered_by = Column(String, default="system")  # system, user, auto
    trigger_condition = Column(String, nullable=True)  # e.g., "health_check_failed_3_times"

    # Version Info
    rolled_back_from = Column(String, nullable=False)  # Version we're rolling back from
    rolled_back_to = Column(String, nullable=False)  # Version we're rolling back to
    from_image = Column(String, nullable=False)
    to_image = Column(String, nullable=False)

    # Status
    status = Column(String, nullable=False, default="pending")  # pending, in_progress, completed, failed
    progress_percent = Column(Integer, default=0)
    current_step = Column(String, nullable=True)

    # Backup Restoration
    backup_restored = Column(Boolean, default=False)
    backup_path = Column(String, nullable=True)
    volume_snapshot_restored = Column(Boolean, default=False)
    config_restored = Column(Boolean, default=False)

    # Previous State
    previous_container_config = Column(JSON, nullable=True)
    previous_environment = Column(JSON, nullable=True)
    previous_volumes = Column(JSON, nullable=True)
    previous_networks = Column(JSON, nullable=True)

    # Execution
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Results
    successful = Column(Boolean, default=False)
    health_check_passed = Column(Boolean, nullable=True)
    container_running_after = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, default=list)

    # Logs
    execution_log = Column(Text, nullable=True)
    health_check_results = Column(JSON, default=list)

    # Metadata
    automatic = Column(Boolean, default=True)
    approved_by = Column(String, nullable=True)
    metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    update = relationship("Update", back_populates="rollback")

    def __repr__(self):
        return f"<Rollback {self.rolled_back_from} -> {self.rolled_back_to} ({self.reason})>"
