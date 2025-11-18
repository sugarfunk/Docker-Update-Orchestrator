from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base
import uuid


class Server(Base):
    """Docker server/host model"""

    __tablename__ = "servers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    hostname = Column(String, nullable=False)
    port = Column(Integer, default=22)
    username = Column(String, default="root")
    ssh_key_path = Column(String, nullable=True)

    # Connection
    is_active = Column(Boolean, default=True)
    last_connected = Column(DateTime(timezone=True), nullable=True)
    connection_status = Column(String, default="unknown")  # connected, disconnected, error

    # Server Info
    os_type = Column(String, nullable=True)  # linux, windows
    os_version = Column(String, nullable=True)
    docker_version = Column(String, nullable=True)
    architecture = Column(String, nullable=True)  # amd64, arm64

    # Resource Info (updated periodically)
    cpu_count = Column(Integer, nullable=True)
    memory_total_mb = Column(Integer, nullable=True)
    disk_total_gb = Column(Integer, nullable=True)
    disk_free_gb = Column(Integer, nullable=True)

    # Network
    tailscale_ip = Column(String, nullable=True)
    local_ip = Column(String, nullable=True)

    # Metadata
    tags = Column(JSON, default=list)  # ["production", "critical", etc]
    notes = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    containers = relationship("Container", back_populates="server", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Server {self.name} ({self.hostname})>"
