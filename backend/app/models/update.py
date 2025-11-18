from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class UpdateStatus(str, Enum):
    """Update execution status"""
    PENDING = "pending"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PULLING_IMAGE = "pulling_image"
    STOPPING_CONTAINER = "stopping_container"
    STARTING_CONTAINER = "starting_container"
    HEALTH_CHECKING = "health_checking"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class UpdateType(str, Enum):
    """Type of update"""
    MAJOR = "major"  # Breaking changes
    MINOR = "minor"  # New features
    PATCH = "patch"  # Bug fixes
    SECURITY = "security"  # Security updates
    UNKNOWN = "unknown"


class Update(Base):
    """Container update model"""

    __tablename__ = "updates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Version Info
    from_version = Column(String, nullable=False)
    to_version = Column(String, nullable=False)
    from_image = Column(String, nullable=False)
    to_image = Column(String, nullable=False)
    from_digest = Column(String, nullable=True)
    to_digest = Column(String, nullable=True)

    # Update Classification
    update_type = Column(SQLEnum(UpdateType), nullable=False, default=UpdateType.UNKNOWN)
    is_security_update = Column(Boolean, default=False)
    severity = Column(String, nullable=True)  # low, medium, high, critical

    # Status
    status = Column(SQLEnum(UpdateStatus), nullable=False, default=UpdateStatus.PENDING, index=True)
    progress_percent = Column(Integer, default=0)
    current_step = Column(String, nullable=True)

    # Changelog
    changelog_id = Column(String, ForeignKey("changelog_analyses.id"), nullable=True)
    changelog_summary = Column(Text, nullable=True)
    breaking_changes = Column(JSON, default=list)
    config_changes_required = Column(JSON, default=list)
    action_items = Column(JSON, default=list)

    # Risk Assessment
    risk_level = Column(String, nullable=True)  # low, medium, high, critical
    risk_factors = Column(JSON, default=list)
    safe_to_auto_update = Column(Boolean, default=False)
    requires_downtime = Column(Boolean, default=False)
    estimated_downtime_seconds = Column(Integer, nullable=True)

    # Execution
    execution_mode = Column(String, default="manual")  # manual, semi-auto, auto
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Backup & Rollback
    backup_created = Column(Boolean, default=False)
    backup_path = Column(String, nullable=True)
    previous_container_config = Column(JSON, nullable=True)
    rollback_available = Column(Boolean, default=False)

    # Health Checks
    health_checks_passed = Column(Boolean, nullable=True)
    health_check_count = Column(Integer, default=0)
    health_check_failures = Column(Integer, default=0)

    # Logs
    execution_log = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, default=list)

    # Approval
    requires_approval = Column(Boolean, default=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)

    # Metadata
    triggered_by = Column(String, default="system")  # system, user, schedule
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    container = relationship("Container", back_populates="updates")
    changelog = relationship("ChangelogAnalysis", backref="updates")
    rollback = relationship("Rollback", back_populates="update", uselist=False)

    def __repr__(self):
        return f"<Update {self.from_version} -> {self.to_version} ({self.status})>"


from sqlalchemy import Boolean
