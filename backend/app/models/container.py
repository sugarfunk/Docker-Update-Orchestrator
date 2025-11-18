from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
import uuid


class Container(Base):
    """Docker container model"""

    __tablename__ = "containers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    server_id = Column(String, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)

    # Container Info
    container_id = Column(String, nullable=False, index=True)  # Docker container ID
    container_name = Column(String, nullable=False, index=True)
    image = Column(String, nullable=False)  # e.g., "nginx:1.25.0"
    image_id = Column(String, nullable=False)

    # Image Details
    registry = Column(String, nullable=True)  # docker.io, ghcr.io, custom
    repository = Column(String, nullable=True)  # e.g., "library/nginx"
    tag = Column(String, nullable=True)  # e.g., "1.25.0" or "latest"
    digest = Column(String, nullable=True)  # Image digest for exact versioning

    # Status
    status = Column(String, nullable=False)  # running, stopped, paused, etc
    state = Column(String, nullable=False)  # created, running, exited, etc
    is_running = Column(Boolean, default=False)

    # Configuration
    compose_file_path = Column(String, nullable=True)  # Path to docker-compose.yml
    compose_service_name = Column(String, nullable=True)  # Service name in compose file
    environment_vars = Column(JSON, default=dict)
    volumes = Column(JSON, default=list)
    networks = Column(JSON, default=list)
    ports = Column(JSON, default=list)
    labels = Column(JSON, default=dict)
    command = Column(String, nullable=True)
    entrypoint = Column(String, nullable=True)

    # Health
    health_status = Column(String, nullable=True)  # healthy, unhealthy, starting
    health_check_url = Column(String, nullable=True)  # Custom health check URL
    health_check_command = Column(String, nullable=True)  # Custom health check command

    # Resource Usage (updated periodically)
    cpu_percent = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    memory_limit_mb = Column(Integer, nullable=True)
    network_rx_bytes = Column(Integer, nullable=True)
    network_tx_bytes = Column(Integer, nullable=True)

    # Update Info
    update_available = Column(Boolean, default=False)
    latest_version = Column(String, nullable=True)
    update_priority = Column(String, default="normal")  # low, normal, high, critical
    last_update_check = Column(DateTime(timezone=True), nullable=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)

    # Service Classification
    service_type = Column(String, nullable=True)  # web, database, proxy, automation, etc
    is_critical = Column(Boolean, default=False)
    auto_update_enabled = Column(Boolean, default=False)
    requires_approval = Column(Boolean, default=True)

    # Metadata
    tags = Column(JSON, default=list)
    notes = Column(Text, nullable=True)
    documentation_url = Column(String, nullable=True)

    # Timestamps
    container_created_at = Column(DateTime(timezone=True), nullable=True)
    container_started_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    server = relationship("Server", back_populates="containers")
    updates = relationship("Update", back_populates="container", cascade="all, delete-orphan")
    health_checks = relationship("HealthCheck", back_populates="container", cascade="all, delete-orphan")
    dependencies_from = relationship(
        "ServiceDependency",
        foreign_keys="ServiceDependency.from_container_id",
        back_populates="from_container",
        cascade="all, delete-orphan"
    )
    dependencies_to = relationship(
        "ServiceDependency",
        foreign_keys="ServiceDependency.to_container_id",
        back_populates="to_container",
        cascade="all, delete-orphan"
    )
    config = relationship("ServiceConfig", back_populates="container", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Container {self.container_name} ({self.image})>"
