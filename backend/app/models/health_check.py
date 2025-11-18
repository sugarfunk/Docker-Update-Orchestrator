from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class HealthCheck(Base):
    """Container health check model"""

    __tablename__ = "health_checks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True)
    update_id = Column(String, ForeignKey("updates.id", ondelete="SET NULL"), nullable=True, index=True)

    # Health Status
    status = Column(SQLEnum(HealthStatus), nullable=False, default=HealthStatus.UNKNOWN)
    is_healthy = Column(Boolean, default=False)

    # Check Details
    check_type = Column(String, nullable=False)  # http, tcp, docker, custom_script, logs
    check_target = Column(String, nullable=True)  # URL, port, command, etc

    # HTTP Checks
    http_url = Column(String, nullable=True)
    http_method = Column(String, default="GET")
    http_expected_status = Column(Integer, default=200)
    http_response_status = Column(Integer, nullable=True)
    http_response_time_ms = Column(Integer, nullable=True)
    http_response_body = Column(Text, nullable=True)

    # TCP Checks
    tcp_host = Column(String, nullable=True)
    tcp_port = Column(Integer, nullable=True)
    tcp_connected = Column(Boolean, nullable=True)
    tcp_response_time_ms = Column(Integer, nullable=True)

    # Docker Health
    docker_health_status = Column(String, nullable=True)  # From Docker's own health check
    container_state = Column(String, nullable=True)
    container_running = Column(Boolean, nullable=True)
    exit_code = Column(Integer, nullable=True)

    # Resource Checks
    cpu_percent = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    memory_percent = Column(Integer, nullable=True)
    cpu_threshold_exceeded = Column(Boolean, default=False)
    memory_threshold_exceeded = Column(Boolean, default=False)

    # Log Analysis
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    critical_errors = Column(JSON, default=list)
    log_sample = Column(Text, nullable=True)

    # Custom Script
    custom_script = Column(Text, nullable=True)
    script_exit_code = Column(Integer, nullable=True)
    script_output = Column(Text, nullable=True)

    # Dependency Checks
    dependencies_healthy = Column(Boolean, nullable=True)
    unhealthy_dependencies = Column(JSON, default=list)

    # Results
    passed = Column(Boolean, default=False)
    failure_reason = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)

    # Timing
    check_started_at = Column(DateTime(timezone=True), nullable=False)
    check_completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    timeout_seconds = Column(Integer, default=30)
    timed_out = Column(Boolean, default=False)

    # Retry
    attempt_number = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    container = relationship("Container", back_populates="health_checks")

    def __repr__(self):
        return f"<HealthCheck {self.check_type} ({self.status})>"
