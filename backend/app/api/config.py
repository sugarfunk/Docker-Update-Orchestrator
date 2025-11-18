from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..core.database import get_db
from ..models import ServiceConfig, GlobalConfig

router = APIRouter()


class ServiceConfigUpdate(BaseModel):
    auto_update_enabled: bool | None = None
    requires_approval: bool | None = None
    health_check_enabled: bool | None = None
    backup_before_update: bool | None = None
    auto_rollback_enabled: bool | None = None


@router.get("/service/{container_id}")
async def get_service_config(container_id: str, db: AsyncSession = Depends(get_db)):
    """Get service configuration"""
    result = await db.execute(
        select(ServiceConfig).where(ServiceConfig.container_id == container_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Service config not found")

    return config


@router.put("/service/{container_id}")
async def update_service_config(
    container_id: str,
    config_update: ServiceConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update service configuration"""
    result = await db.execute(
        select(ServiceConfig).where(ServiceConfig.container_id == container_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create new config
        config = ServiceConfig(container_id=container_id)
        db.add(config)

    # Update fields
    if config_update.auto_update_enabled is not None:
        config.auto_update_enabled = config_update.auto_update_enabled
    if config_update.requires_approval is not None:
        config.requires_approval = config_update.requires_approval
    if config_update.health_check_enabled is not None:
        config.health_check_enabled = config_update.health_check_enabled
    if config_update.backup_before_update is not None:
        config.backup_before_update = config_update.backup_before_update
    if config_update.auto_rollback_enabled is not None:
        config.auto_rollback_enabled = config_update.auto_rollback_enabled

    await db.commit()
    await db.refresh(config)

    return {"success": True, "config": config}


@router.get("/global")
async def get_global_config(db: AsyncSession = Depends(get_db)):
    """Get global configuration"""
    result = await db.execute(select(GlobalConfig))
    configs = result.scalars().all()

    return {config.key: config.value for config in configs}


@router.put("/global/{key}")
async def update_global_config(key: str, value: dict, db: AsyncSession = Depends(get_db)):
    """Update global configuration"""
    result = await db.execute(select(GlobalConfig).where(GlobalConfig.key == key))
    config = result.scalar_one_or_none()

    if not config:
        config = GlobalConfig(key=key)
        db.add(config)

    config.value = value
    await db.commit()

    return {"success": True, "key": key, "value": value}
