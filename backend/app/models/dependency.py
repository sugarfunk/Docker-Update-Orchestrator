from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class DependencyType(str, Enum):
    """Type of dependency between services"""
    DATABASE = "database"  # Service depends on a database
    API = "api"  # Service calls another service's API
    MESSAGE_QUEUE = "message_queue"  # Service uses queue/messaging
    CACHE = "cache"  # Service uses cache
    STORAGE = "storage"  # Service uses shared storage
    REVERSE_PROXY = "reverse_proxy"  # Service is behind proxy
    NETWORK = "network"  # Service shares network
    VOLUME = "volume"  # Service shares volume
    AUTHENTICATION = "authentication"  # Service depends on auth service
    SERVICE_DISCOVERY = "service_discovery"  # Service uses discovery
    CONFIG = "config"  # Service depends on config service
    MONITORING = "monitoring"  # Service reports to monitoring
    OTHER = "other"


class ServiceDependency(Base):
    """Service dependency mapping model"""

    __tablename__ = "service_dependencies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Dependency Relationship
    from_container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True)
    to_container_id = Column(String, ForeignKey("containers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Dependency Info
    dependency_type = Column(SQLEnum(DependencyType), nullable=False, default=DependencyType.OTHER)
    is_critical = Column(Boolean, default=True)  # If true, service won't work without dependency
    is_optional = Column(Boolean, default=False)

    # Detection
    auto_detected = Column(Boolean, default=False)
    detection_method = Column(String, nullable=True)  # network_analysis, env_var, compose_file, manual
    confidence_score = Column(Integer, nullable=True)  # 0-100

    # Connection Details
    connection_string = Column(String, nullable=True)
    connection_port = Column(Integer, nullable=True)
    connection_protocol = Column(String, nullable=True)  # http, tcp, grpc, etc

    # Health Impact
    affects_health = Column(Boolean, default=True)
    health_check_dependency = Column(Boolean, default=True)

    # Update Ordering
    must_update_before = Column(Boolean, default=False)  # Dependency must be updated first
    startup_delay_seconds = Column(Integer, default=0)  # Wait time after dependency starts

    # Metadata
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    verified = Column(Boolean, default=False)
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    from_container = relationship(
        "Container",
        foreign_keys=[from_container_id],
        back_populates="dependencies_from"
    )
    to_container = relationship(
        "Container",
        foreign_keys=[to_container_id],
        back_populates="dependencies_to"
    )

    def __repr__(self):
        return f"<ServiceDependency {self.from_container_id} -> {self.to_container_id} ({self.dependency_type})>"
