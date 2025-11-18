from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Docker Update Orchestrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://orchestrator:orchestrator@postgres:5432/orchestrator"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Security
    SECRET_KEY: str = "change-this-to-a-secure-random-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Docker Servers
    DOCKER_SERVERS: str = "workhorse1,workhorse2,minideb,mediabeelink,hetzner-vps"
    SSH_KEY_PATH: str = "/root/.ssh/id_rsa"
    SSH_USERNAME: str = "root"
    SSH_PORT: int = 22

    # Update Settings
    MAX_CONCURRENT_UPDATES: int = 3
    UPDATE_CHECK_INTERVAL_HOURS: int = 6
    HEALTH_CHECK_TIMEOUT_SECONDS: int = 300
    HEALTH_CHECK_RETRIES: int = 3
    ROLLBACK_ON_FAILURE: bool = True
    BACKUP_RETENTION_DAYS: int = 30

    # LLM Configuration
    LLM_PROVIDER: str = "anthropic"  # anthropic, openai, ollama, gemini
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # LLM Model Selection
    LLM_MODEL_PRIMARY: str = "claude-3-5-sonnet-20241022"
    LLM_MODEL_FALLBACK: str = "gpt-4-turbo-preview"
    LLM_MODEL_LOCAL: str = "llama2"
    USE_LOCAL_FOR_SENSITIVE: bool = True

    # Notifications
    NTFY_ENABLED: bool = True
    NTFY_TOPIC: str = "docker-updates"
    NTFY_SERVER: str = "https://ntfy.sh"

    EMAIL_ENABLED: bool = False
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    EMAIL_TO: List[str] = []

    WEBHOOK_ENABLED: bool = False
    WEBHOOK_URLS: List[str] = []

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
