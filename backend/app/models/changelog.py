from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, Enum as SQLEnum, Boolean
from sqlalchemy.sql import func
from ..core.database import Base
from enum import Enum
import uuid


class RiskLevel(str, Enum):
    """Risk level for updates"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangelogAnalysis(Base):
    """Changelog analysis model"""

    __tablename__ = "changelog_analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Image/Version Info
    image_name = Column(String, nullable=False, index=True)
    from_version = Column(String, nullable=False)
    to_version = Column(String, nullable=False)

    # Changelog Source
    changelog_url = Column(String, nullable=True)
    changelog_source = Column(String, nullable=True)  # github, dockerhub, project_site
    raw_changelog = Column(Text, nullable=True)

    # LLM Analysis
    llm_provider = Column(String, nullable=False)  # anthropic, openai, ollama, etc
    llm_model = Column(String, nullable=False)
    analysis_date = Column(DateTime(timezone=True), server_default=func.now())
    tokens_used = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)

    # Summary
    executive_summary = Column(Text, nullable=True)
    user_facing_changes = Column(JSON, default=list)
    technical_changes = Column(JSON, default=list)

    # Breaking Changes
    has_breaking_changes = Column(Boolean, default=False)
    breaking_changes = Column(JSON, default=list)  # List of BreakingChange objects

    # Configuration & Requirements
    config_changes_required = Column(JSON, default=list)
    env_var_changes = Column(JSON, default=list)
    volume_changes = Column(JSON, default=list)
    port_changes = Column(JSON, default=list)
    minimum_version_requirements = Column(JSON, default=dict)

    # Dependencies
    dependency_updates = Column(JSON, default=list)
    database_migrations_required = Column(Boolean, default=False)
    migration_notes = Column(Text, nullable=True)

    # Risk Assessment
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, default=RiskLevel.MEDIUM)
    risk_factors = Column(JSON, default=list)
    safe_to_auto_update = Column(Boolean, default=False)
    recommended_action = Column(Text, nullable=True)

    # Deprecations & Removals
    deprecated_features = Column(JSON, default=list)
    removed_features = Column(JSON, default=list)
    deprecated_apis = Column(JSON, default=list)

    # New Features
    new_features = Column(JSON, default=list)
    improvements = Column(JSON, default=list)
    bug_fixes = Column(JSON, default=list)

    # Security
    security_fixes = Column(JSON, default=list)
    cve_ids = Column(JSON, default=list)
    security_severity = Column(String, nullable=True)

    # Testing & Validation
    testing_recommendations = Column(JSON, default=list)
    rollback_complexity = Column(String, nullable=True)  # easy, moderate, difficult
    estimated_update_time_minutes = Column(Integer, nullable=True)

    # Action Items
    action_items = Column(JSON, default=list)
    pre_update_steps = Column(JSON, default=list)
    post_update_steps = Column(JSON, default=list)

    # Metadata
    analysis_confidence = Column(String, default="medium")  # low, medium, high
    analysis_notes = Column(Text, nullable=True)
    requires_human_review = Column(Boolean, default=False)
    human_reviewed = Column(Boolean, default=False)
    human_reviewer = Column(String, nullable=True)
    human_review_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ChangelogAnalysis {self.image_name} {self.from_version} -> {self.to_version}>"


class BreakingChange(Base):
    """Breaking change detail model"""

    __tablename__ = "breaking_changes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    changelog_id = Column(String, ForeignKey("changelog_analyses.id", ondelete="CASCADE"), nullable=False)

    # Change Details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)  # api, config, behavior, dependency, etc
    severity = Column(String, nullable=False)  # low, medium, high, critical

    # Impact
    affected_components = Column(JSON, default=list)
    workaround = Column(Text, nullable=True)
    migration_steps = Column(JSON, default=list)

    # Metadata
    reference_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<BreakingChange {self.title} ({self.severity})>"


from sqlalchemy import Float, ForeignKey
