from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
import uuid


class ServiceConfig(Base):
    """Per-service configuration model"""

    __tablename__ = "service_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Auto-Update Settings
    auto_update_enabled = Column(Boolean, default=False)
    auto_update_types = Column(JSON, default=list)  # ["patch", "security"]
    requires_approval = Column(Boolean, default=True)
    approval_for_types = Column(JSON, default=list)  # ["major", "minor"]

    # Update Windows
    update_window_enabled = Column(Boolean, default=False)
    preferred_update_days = Column(JSON, default=list)  # [0-6, 0=Monday]
    preferred_update_hours = Column(JSON, default=list)  # [0-23]
    preferred_update_time = Column(String, nullable=True)  # e.g., "02:00"
    timezone = Column(String, default="UTC")

    # Maintenance Windows
    maintenance_windows = Column(JSON, default=list)
    # Example: [{"start": "2024-01-01T00:00:00Z", "end": "2024-01-01T06:00:00Z"}]
    blackout_windows = Column(JSON, default=list)
    # Times when updates should NEVER happen

    # Health Check Configuration
    health_check_enabled = Column(Boolean, default=True)
    health_check_type = Column(String, default="docker")  # http, tcp, docker, custom
    health_check_url = Column(String, nullable=True)
    health_check_port = Column(Integer, nullable=True)
    health_check_path = Column(String, default="/health")
    health_check_method = Column(String, default="GET")
    health_check_expected_status = Column(Integer, default=200)
    health_check_timeout_seconds = Column(Integer, default=30)
    health_check_interval_seconds = Column(Integer, default=10)
    health_check_retries = Column(Integer, default=3)
    health_check_startup_delay_seconds = Column(Integer, default=10)
    custom_health_check_script = Column(Text, nullable=True)

    # Resource Thresholds
    cpu_threshold_percent = Column(Integer, default=90)
    memory_threshold_percent = Column(Integer, default=90)
    monitor_resources = Column(Boolean, default=True)

    # Backup Settings
    backup_before_update = Column(Boolean, default=True)
    backup_volumes = Column(JSON, default=list)  # List of volume names to backup
    backup_retention_count = Column(Integer, default=5)

    # Rollback Settings
    auto_rollback_enabled = Column(Boolean, default=True)
    rollback_on_health_check_failure = Column(Boolean, default=True)
    rollback_on_crash = Column(Boolean, default=True)
    rollback_timeout_minutes = Column(Integer, default=10)

    # Pre/Post Update Scripts
    pre_update_script = Column(Text, nullable=True)
    post_update_script = Column(Text, nullable=True)
    pre_update_commands = Column(JSON, default=list)
    post_update_commands = Column(JSON, default=list)

    # Dependency Handling
    update_dependencies_first = Column(Boolean, default=True)
    wait_for_dependencies = Column(Boolean, default=True)
    dependency_startup_delay_seconds = Column(Integer, default=30)

    # Notification Settings
    notify_on_update_available = Column(Boolean, default=True)
    notify_on_update_started = Column(Boolean, default=False)
    notify_on_update_completed = Column(Boolean, default=True)
    notify_on_update_failed = Column(Boolean, default=True)
    notify_on_breaking_changes = Column(Boolean, default=True)
    notify_on_rollback = Column(Boolean, default=True)
    notification_channels = Column(JSON, default=list)  # ["ntfy", "email"]

    # Update Strategy
    update_strategy = Column(String, default="recreate")  # recreate, rolling, blue_green
    min_uptime_before_success_seconds = Column(Integer, default=300)  # 5 minutes
    max_update_duration_minutes = Column(Integer, default=30)

    # Risk Management
    max_risk_level = Column(String, default="high")  # low, medium, high, critical
    block_breaking_changes = Column(Boolean, default=False)
    require_changelog_review = Column(Boolean, default=False)

    # Metadata
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    custom_settings = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    container = relationship("Container", back_populates="config")

    def __repr__(self):
        return f"<ServiceConfig for {self.container_id}>"


class GlobalConfig(Base):
    """Global system configuration model"""

    __tablename__ = "global_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # updates, notifications, llm, etc

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<GlobalConfig {self.key}>"
