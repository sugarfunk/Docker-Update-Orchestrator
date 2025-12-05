import os
import tarfile
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Container, Server
from .docker_service import docker_service

logger = logging.getLogger(__name__)


class BackupService:
    """Service for creating and managing container backups"""

    def __init__(self):
        self.backup_root = "/var/lib/docker-orchestrator/backups"
        self.retention_days = 30

    async def create_backup(
        self,
        container: Container,
        server: Server,
        session: AsyncSession
    ) -> Optional[str]:
        """Create backup of container volumes and configuration"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{container.container_name}_{timestamp}"
            backup_dir = Path(self.backup_root) / server.name / container.container_name

            # Create backup directory
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / f"{backup_name}.tar.gz"

            logger.info(f"Creating backup: {backup_path}")

            # Create backup archive
            with tarfile.open(backup_path, "w:gz") as tar:
                # Save container configuration
                config = {
                    'container_name': container.container_name,
                    'image': container.image,
                    'image_id': container.image_id,
                    'tag': container.tag,
                    'digest': container.digest,
                    'environment': container.environment_vars,
                    'volumes': container.volumes,
                    'networks': container.networks,
                    'ports': container.ports,
                    'labels': container.labels,
                    'command': container.command,
                    'entrypoint': container.entrypoint,
                    'created_at': container.created_at.isoformat() if container.created_at else None,
                    'backup_timestamp': timestamp
                }

                # Write config to temp file and add to archive
                config_file = backup_dir / f"{backup_name}_config.json"
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)

                tar.add(config_file, arcname="container_config.json")
                config_file.unlink()  # Remove temp file

                # TODO: Backup volumes
                # This would require:
                # 1. Connect to server via SSH
                # 2. Create tar of volume directories
                # 3. Transfer to backup location
                # For now, we just save the configuration

            logger.info(f"Backup created: {backup_path}")

            # Clean old backups
            await self._cleanup_old_backups(backup_dir)

            return str(backup_path)

        except Exception as e:
            logger.error(f"Backup creation failed: {str(e)}")
            return None

    async def restore_backup(
        self,
        backup_path: str,
        container: Container,
        server: Server
    ) -> bool:
        """Restore container from backup"""
        try:
            logger.info(f"Restoring from backup: {backup_path}")

            if not Path(backup_path).exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            # Extract backup
            with tarfile.open(backup_path, "r:gz") as tar:
                # Extract config
                tar.extract("container_config.json", path="/tmp")

                with open("/tmp/container_config.json", 'r') as f:
                    config = json.load(f)

                # Restore container configuration
                container.image = config.get('image')
                container.image_id = config.get('image_id')
                container.tag = config.get('tag')
                container.digest = config.get('digest')
                container.environment_vars = config.get('environment')
                container.volumes = config.get('volumes')
                container.networks = config.get('networks')
                container.ports = config.get('ports')
                container.labels = config.get('labels')
                container.command = config.get('command')
                container.entrypoint = config.get('entrypoint')

                # TODO: Restore volumes
                # This would require SSH to server and extraction of volume data

                # Cleanup
                os.remove("/tmp/container_config.json")

            logger.info("Backup restored successfully")
            return True

        except Exception as e:
            logger.error(f"Backup restoration failed: {str(e)}")
            return False

    async def list_backups(
        self,
        container: Container,
        server: Server
    ) -> List[Dict]:
        """List all backups for a container"""
        backups = []

        try:
            backup_dir = Path(self.backup_root) / server.name / container.container_name

            if not backup_dir.exists():
                return backups

            for backup_file in sorted(backup_dir.glob("*.tar.gz"), reverse=True):
                stat = backup_file.stat()
                backups.append({
                    'path': str(backup_file),
                    'name': backup_file.name,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created_at': datetime.fromtimestamp(stat.st_mtime),
                    'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                })

        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")

        return backups

    async def _cleanup_old_backups(self, backup_dir: Path):
        """Clean up old backups based on retention policy"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)

            for backup_file in backup_dir.glob("*.tar.gz"):
                stat = backup_file.stat()
                file_date = datetime.fromtimestamp(stat.st_mtime)

                if file_date < cutoff_date:
                    logger.info(f"Removing old backup: {backup_file.name}")
                    backup_file.unlink()

        except Exception as e:
            logger.error(f"Error cleaning up backups: {str(e)}")

    async def get_backup_size(self, server: Server) -> Dict:
        """Get total backup size for a server"""
        try:
            backup_dir = Path(self.backup_root) / server.name

            if not backup_dir.exists():
                return {'total_size_mb': 0, 'backup_count': 0}

            total_size = 0
            backup_count = 0

            for backup_file in backup_dir.rglob("*.tar.gz"):
                total_size += backup_file.stat().st_size
                backup_count += 1

            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'backup_count': backup_count
            }

        except Exception as e:
            logger.error(f"Error calculating backup size: {str(e)}")
            return {'total_size_mb': 0, 'backup_count': 0}


# Global instance
backup_service = BackupService()
