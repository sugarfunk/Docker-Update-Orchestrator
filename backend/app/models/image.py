from sqlalchemy import Column, String, DateTime, Integer, JSON, Boolean
from sqlalchemy.sql import func
from ..core.database import Base
import uuid


class Image(Base):
    """Docker image tracking model"""

    __tablename__ = "images"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Image Info
    registry = Column(String, nullable=False, index=True)  # docker.io, ghcr.io, etc
    repository = Column(String, nullable=False, index=True)  # e.g., "library/nginx"
    full_name = Column(String, nullable=False, unique=True, index=True)  # e.g., "docker.io/library/nginx"

    # Latest Version
    latest_tag = Column(String, nullable=True)
    latest_digest = Column(String, nullable=True)
    latest_version = Column(String, nullable=True)  # Semantic version if available

    # Available Versions
    available_tags = Column(JSON, default=list)  # List of all available tags
    version_history = Column(JSON, default=list)  # Parsed version history

    # Update Tracking
    last_checked = Column(DateTime(timezone=True), nullable=True)
    check_interval_hours = Column(Integer, default=6)
    update_frequency = Column(String, default="unknown")  # daily, weekly, monthly, rarely

    # Project Info
    github_repo = Column(String, nullable=True)  # e.g., "nginx/nginx"
    project_url = Column(String, nullable=True)
    documentation_url = Column(String, nullable=True)
    changelog_url = Column(String, nullable=True)

    # Status
    is_deprecated = Column(Boolean, default=False)
    is_abandoned = Column(Boolean, default=False)
    deprecation_notice = Column(String, nullable=True)

    # Metadata
    description = Column(String, nullable=True)
    maintainer = Column(String, nullable=True)
    license = Column(String, nullable=True)
    architectures = Column(JSON, default=list)  # ["amd64", "arm64"]

    # Statistics
    pull_count = Column(Integer, nullable=True)
    star_count = Column(Integer, nullable=True)
    last_pushed = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Image {self.full_name}:{self.latest_tag}>"
