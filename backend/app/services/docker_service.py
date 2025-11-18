import docker
import paramiko
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)


class DockerService:
    """Service for interacting with Docker on remote servers"""

    def __init__(self):
        self.ssh_clients = {}
        self.docker_clients = {}

    def connect_to_server(self, hostname: str, port: int = 22, username: str = "root",
                          ssh_key_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Connect to a remote server via SSH and create Docker client
        Returns: (success, message)
        """
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if ssh_key_path:
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    key_filename=ssh_key_path,
                    timeout=10
                )
            else:
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    timeout=10
                )

            self.ssh_clients[hostname] = ssh

            # Create Docker client over SSH
            # Use SSH tunnel to connect to Docker socket
            docker_client = docker.DockerClient(base_url=f'ssh://{username}@{hostname}')

            # Test connection
            docker_client.ping()

            self.docker_clients[hostname] = docker_client

            logger.info(f"Successfully connected to Docker on {hostname}")
            return True, "Connected successfully"

        except Exception as e:
            logger.error(f"Failed to connect to {hostname}: {str(e)}")
            return False, str(e)

    def disconnect_from_server(self, hostname: str):
        """Disconnect from a server"""
        if hostname in self.docker_clients:
            try:
                self.docker_clients[hostname].close()
            except:
                pass
            del self.docker_clients[hostname]

        if hostname in self.ssh_clients:
            try:
                self.ssh_clients[hostname].close()
            except:
                pass
            del self.ssh_clients[hostname]

    def get_server_info(self, hostname: str) -> Optional[Dict]:
        """Get Docker server information"""
        if hostname not in self.docker_clients:
            return None

        try:
            client = self.docker_clients[hostname]
            info = client.info()
            version = client.version()

            return {
                "docker_version": version.get("Version"),
                "os_type": info.get("OSType"),
                "os_version": info.get("OperatingSystem"),
                "architecture": info.get("Architecture"),
                "cpu_count": info.get("NCPU"),
                "memory_total_mb": info.get("MemTotal", 0) // (1024 * 1024),
                "containers_running": info.get("ContainersRunning"),
                "containers_total": info.get("Containers"),
                "images_count": info.get("Images"),
            }
        except Exception as e:
            logger.error(f"Failed to get server info for {hostname}: {str(e)}")
            return None

    def list_containers(self, hostname: str, all_containers: bool = True) -> List[Dict]:
        """List all containers on a server"""
        if hostname not in self.docker_clients:
            logger.error(f"Not connected to {hostname}")
            return []

        try:
            client = self.docker_clients[hostname]
            containers = client.containers.list(all=all_containers)

            result = []
            for container in containers:
                try:
                    attrs = container.attrs
                    config = attrs.get("Config", {})
                    state = attrs.get("State", {})
                    network_settings = attrs.get("NetworkSettings", {})
                    host_config = attrs.get("HostConfig", {})

                    # Parse image name
                    image_full = config.get("Image", "")
                    image_parts = self._parse_image_name(image_full)

                    # Get resource stats
                    stats = None
                    try:
                        if state.get("Running"):
                            stats = container.stats(stream=False)
                    except:
                        pass

                    container_info = {
                        "container_id": container.id,
                        "container_short_id": container.short_id,
                        "name": container.name,
                        "image": image_full,
                        "image_id": attrs.get("Image"),
                        "registry": image_parts["registry"],
                        "repository": image_parts["repository"],
                        "tag": image_parts["tag"],
                        "status": container.status,
                        "state": state.get("Status"),
                        "is_running": state.get("Running", False),
                        "created": attrs.get("Created"),
                        "started_at": state.get("StartedAt"),
                        "environment": config.get("Env", []),
                        "labels": config.get("Labels", {}),
                        "ports": self._parse_ports(network_settings.get("Ports", {})),
                        "networks": list(network_settings.get("Networks", {}).keys()),
                        "volumes": self._parse_volumes(host_config.get("Binds", [])),
                        "command": config.get("Cmd"),
                        "entrypoint": config.get("Entrypoint"),
                        "health": state.get("Health", {}),
                        "restart_policy": host_config.get("RestartPolicy", {}),
                    }

                    # Add resource stats if available
                    if stats:
                        container_info["stats"] = self._parse_stats(stats)

                    result.append(container_info)

                except Exception as e:
                    logger.error(f"Error parsing container {container.id}: {str(e)}")
                    continue

            return result

        except Exception as e:
            logger.error(f"Failed to list containers on {hostname}: {str(e)}")
            return []

    def get_container_logs(self, hostname: str, container_id: str,
                          tail: int = 100, since: Optional[datetime] = None) -> Optional[str]:
        """Get container logs"""
        if hostname not in self.docker_clients:
            return None

        try:
            client = self.docker_clients[hostname]
            container = client.containers.get(container_id)

            kwargs = {"tail": tail, "timestamps": True}
            if since:
                kwargs["since"] = since

            logs = container.logs(**kwargs)
            return logs.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Failed to get logs for {container_id} on {hostname}: {str(e)}")
            return None

    def pull_image(self, hostname: str, image: str) -> Tuple[bool, str]:
        """Pull a Docker image"""
        if hostname not in self.docker_clients:
            return False, f"Not connected to {hostname}"

        try:
            client = self.docker_clients[hostname]
            client.images.pull(image)
            logger.info(f"Successfully pulled image {image} on {hostname}")
            return True, "Image pulled successfully"

        except Exception as e:
            logger.error(f"Failed to pull image {image} on {hostname}: {str(e)}")
            return False, str(e)

    def stop_container(self, hostname: str, container_id: str, timeout: int = 10) -> Tuple[bool, str]:
        """Stop a container"""
        if hostname not in self.docker_clients:
            return False, f"Not connected to {hostname}"

        try:
            client = self.docker_clients[hostname]
            container = client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Successfully stopped container {container_id} on {hostname}")
            return True, "Container stopped"

        except Exception as e:
            logger.error(f"Failed to stop container {container_id} on {hostname}: {str(e)}")
            return False, str(e)

    def start_container(self, hostname: str, container_id: str) -> Tuple[bool, str]:
        """Start a container"""
        if hostname not in self.docker_clients:
            return False, f"Not connected to {hostname}"

        try:
            client = self.docker_clients[hostname]
            container = client.containers.get(container_id)
            container.start()
            logger.info(f"Successfully started container {container_id} on {hostname}")
            return True, "Container started"

        except Exception as e:
            logger.error(f"Failed to start container {container_id} on {hostname}: {str(e)}")
            return False, str(e)

    def remove_container(self, hostname: str, container_id: str, force: bool = False) -> Tuple[bool, str]:
        """Remove a container"""
        if hostname not in self.docker_clients:
            return False, f"Not connected to {hostname}"

        try:
            client = self.docker_clients[hostname]
            container = client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Successfully removed container {container_id} on {hostname}")
            return True, "Container removed"

        except Exception as e:
            logger.error(f"Failed to remove container {container_id} on {hostname}: {str(e)}")
            return False, str(e)

    def create_container(self, hostname: str, image: str, **kwargs) -> Tuple[bool, str, Optional[str]]:
        """Create a new container"""
        if hostname not in self.docker_clients:
            return False, f"Not connected to {hostname}", None

        try:
            client = self.docker_clients[hostname]
            container = client.containers.create(image, **kwargs)
            logger.info(f"Successfully created container from {image} on {hostname}")
            return True, "Container created", container.id

        except Exception as e:
            logger.error(f"Failed to create container from {image} on {hostname}: {str(e)}")
            return False, str(e), None

    def _parse_image_name(self, image: str) -> Dict[str, str]:
        """Parse Docker image name into components"""
        registry = "docker.io"
        repository = image
        tag = "latest"

        # Check for tag
        if ":" in image:
            repository, tag = image.rsplit(":", 1)

        # Check for registry
        if "/" in repository:
            parts = repository.split("/", 1)
            if "." in parts[0] or ":" in parts[0] or parts[0] == "localhost":
                registry = parts[0]
                repository = parts[1]

        # Handle Docker Hub library images
        if registry == "docker.io" and "/" not in repository:
            repository = f"library/{repository}"

        return {
            "registry": registry,
            "repository": repository,
            "tag": tag,
            "full": f"{registry}/{repository}:{tag}"
        }

    def _parse_ports(self, ports: Dict) -> List[Dict]:
        """Parse container ports"""
        result = []
        for container_port, host_bindings in ports.items():
            if host_bindings:
                for binding in host_bindings:
                    result.append({
                        "container_port": container_port,
                        "host_ip": binding.get("HostIp", "0.0.0.0"),
                        "host_port": binding.get("HostPort")
                    })
        return result

    def _parse_volumes(self, binds: List[str]) -> List[Dict]:
        """Parse container volumes"""
        result = []
        for bind in binds:
            parts = bind.split(":")
            if len(parts) >= 2:
                result.append({
                    "host_path": parts[0],
                    "container_path": parts[1],
                    "mode": parts[2] if len(parts) > 2 else "rw"
                })
        return result

    def _parse_stats(self, stats: Dict) -> Dict:
        """Parse container resource stats"""
        try:
            # CPU calculation
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_count = stats["cpu_stats"].get("online_cpus", 1)

            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100

            # Memory calculation
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 0)
            memory_percent = 0.0
            if memory_limit > 0:
                memory_percent = (memory_usage / memory_limit) * 100

            # Network calculation
            networks = stats.get("networks", {})
            rx_bytes = sum(net.get("rx_bytes", 0) for net in networks.values())
            tx_bytes = sum(net.get("tx_bytes", 0) for net in networks.values())

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage_mb": round(memory_usage / (1024 * 1024), 2),
                "memory_limit_mb": round(memory_limit / (1024 * 1024), 2),
                "memory_percent": round(memory_percent, 2),
                "network_rx_bytes": rx_bytes,
                "network_tx_bytes": tx_bytes
            }
        except Exception as e:
            logger.error(f"Error parsing stats: {str(e)}")
            return {}

    def cleanup(self):
        """Cleanup all connections"""
        for hostname in list(self.docker_clients.keys()):
            self.disconnect_from_server(hostname)


# Global instance
docker_service = DockerService()
