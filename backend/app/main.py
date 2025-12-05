from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .core.config import settings
from .core.database import init_db, close_db
from .api import servers, containers, updates, health, notifications, config as config_api, dependencies, rollback

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown"""
    # Startup
    logger.info("Starting Docker Update Orchestrator...")
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(servers.router, prefix=f"{settings.API_V1_PREFIX}/servers", tags=["Servers"])
app.include_router(containers.router, prefix=f"{settings.API_V1_PREFIX}/containers", tags=["Containers"])
app.include_router(updates.router, prefix=f"{settings.API_V1_PREFIX}/updates", tags=["Updates"])
app.include_router(dependencies.router, prefix=f"{settings.API_V1_PREFIX}/dependencies", tags=["Dependencies"])
app.include_router(rollback.router, prefix=f"{settings.API_V1_PREFIX}/rollback", tags=["Rollback"])
app.include_router(health.router, prefix=f"{settings.API_V1_PREFIX}/health", tags=["Health"])
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
app.include_router(config_api.router, prefix=f"{settings.API_V1_PREFIX}/config", tags=["Configuration"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/api/v1/status")
async def status():
    """System status endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }
