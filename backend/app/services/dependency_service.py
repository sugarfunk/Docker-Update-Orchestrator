import re
import yaml
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models import Container, ServiceDependency, DependencyType

logger = logging.getLogger(__name__)


class DependencyService:
    """Service for analyzing and detecting service dependencies"""

    def __init__(self):
        self.dependency_patterns = {
            'database': [
                r'postgres', r'postgresql', r'mysql', r'mariadb', r'mongodb',
                r'redis', r'memcached', r'elasticsearch'
            ],
            'message_queue': [
                r'rabbitmq', r'kafka', r'nats', r'activemq'
            ],
            'proxy': [
                r'nginx', r'traefik', r'caddy', r'haproxy', r'envoy'
            ],
            'cache': [
                r'redis', r'memcached', r'varnish'
            ]
        }

    async def analyze_all_dependencies(self, session: AsyncSession, server_id: Optional[str] = None):
        """Analyze dependencies for all containers"""
        try:
            # Get all containers
            query = select(Container)
            if server_id:
                query = query.where(Container.server_id == server_id)

            result = await session.execute(query)
            containers = result.scalars().all()

            logger.info(f"Analyzing dependencies for {len(containers)} containers")

            dependencies_found = 0

            for container in containers:
                deps = await self._analyze_container_dependencies(container, containers, session)
                dependencies_found += len(deps)

            await session.commit()
            logger.info(f"Found {dependencies_found} dependencies")

            return dependencies_found

        except Exception as e:
            logger.error(f"Error analyzing dependencies: {str(e)}")
            await session.rollback()
            return 0

    async def _analyze_container_dependencies(
        self,
        container: Container,
        all_containers: List[Container],
        session: AsyncSession
    ) -> List[ServiceDependency]:
        """Analyze dependencies for a single container"""
        dependencies = []

        # 1. Check environment variables for connection strings
        env_deps = self._analyze_environment_variables(container, all_containers)
        dependencies.extend(env_deps)

        # 2. Check shared networks
        network_deps = self._analyze_shared_networks(container, all_containers)
        dependencies.extend(network_deps)

        # 3. Check shared volumes
        volume_deps = self._analyze_shared_volumes(container, all_containers)
        dependencies.extend(volume_deps)

        # 4. Analyze docker-compose dependencies
        if container.compose_file_path:
            compose_deps = await self._analyze_compose_file(container, all_containers)
            dependencies.extend(compose_deps)

        # 5. Detect common service patterns
        pattern_deps = self._detect_service_patterns(container, all_containers)
        dependencies.extend(pattern_deps)

        # Store dependencies in database
        for dep in dependencies:
            # Check if dependency already exists
            existing = await session.execute(
                select(ServiceDependency).where(
                    ServiceDependency.from_container_id == container.id,
                    ServiceDependency.to_container_id == dep['to_container_id'],
                    ServiceDependency.dependency_type == dep['type']
                )
            )
            if not existing.scalar_one_or_none():
                dependency = ServiceDependency(
                    from_container_id=container.id,
                    to_container_id=dep['to_container_id'],
                    dependency_type=dep['type'],
                    is_critical=dep.get('is_critical', True),
                    auto_detected=True,
                    detection_method=dep.get('detection_method', 'auto'),
                    confidence_score=dep.get('confidence_score', 70),
                    connection_string=dep.get('connection_string'),
                    connection_port=dep.get('connection_port'),
                    description=dep.get('description')
                )
                session.add(dependency)

        return dependencies

    def _analyze_environment_variables(
        self,
        container: Container,
        all_containers: List[Container]
    ) -> List[Dict]:
        """Analyze environment variables for connection strings"""
        dependencies = []

        if not container.environment_vars:
            return dependencies

        # Create a mapping of container names to containers
        container_map = {c.container_name: c for c in all_containers}

        # Common environment variable patterns
        patterns = {
            'database': [
                r'DATABASE_URL', r'DB_HOST', r'DB_NAME', r'POSTGRES_HOST',
                r'MYSQL_HOST', r'MONGO_HOST', r'REDIS_HOST', r'REDIS_URL'
            ],
            'api': [
                r'API_URL', r'API_HOST', r'API_ENDPOINT', r'SERVICE_URL'
            ],
            'message_queue': [
                r'RABBITMQ_HOST', r'KAFKA_HOST', r'NATS_URL', r'AMQP_URL'
            ],
            'cache': [
                r'CACHE_HOST', r'REDIS_HOST', r'MEMCACHED_HOST'
            ]
        }

        for env_var in container.environment_vars:
            if isinstance(env_var, str) and '=' in env_var:
                key, value = env_var.split('=', 1)

                # Check if value contains reference to another container
                for other_container in all_containers:
                    if other_container.id == container.id:
                        continue

                    # Check if container name is in the value
                    if other_container.container_name in value:
                        # Determine dependency type
                        dep_type = self._determine_dependency_type(key, value, other_container)

                        dependencies.append({
                            'to_container_id': other_container.id,
                            'type': dep_type,
                            'is_critical': True,
                            'detection_method': 'environment_variable',
                            'confidence_score': 90,
                            'connection_string': value,
                            'description': f"References {other_container.container_name} in {key}"
                        })

        return dependencies

    def _analyze_shared_networks(
        self,
        container: Container,
        all_containers: List[Container]
    ) -> List[Dict]:
        """Analyze shared Docker networks"""
        dependencies = []

        if not container.networks:
            return dependencies

        container_networks = set(container.networks)

        for other_container in all_containers:
            if other_container.id == container.id or not other_container.networks:
                continue

            # Check if containers share a network
            shared_networks = container_networks.intersection(set(other_container.networks))

            if shared_networks:
                # Determine if this is likely a dependency
                dep_type = self._infer_dependency_from_services(container, other_container)

                if dep_type:
                    dependencies.append({
                        'to_container_id': other_container.id,
                        'type': dep_type,
                        'is_critical': False,
                        'detection_method': 'shared_network',
                        'confidence_score': 50,
                        'description': f"Shares network(s): {', '.join(shared_networks)}"
                    })

        return dependencies

    def _analyze_shared_volumes(
        self,
        container: Container,
        all_containers: List[Container]
    ) -> List[Dict]:
        """Analyze shared Docker volumes"""
        dependencies = []

        if not container.volumes:
            return dependencies

        for other_container in all_containers:
            if other_container.id == container.id or not other_container.volumes:
                continue

            # Check for shared volumes
            for vol1 in container.volumes:
                for vol2 in other_container.volumes:
                    if isinstance(vol1, dict) and isinstance(vol2, dict):
                        # Check if same host path
                        if vol1.get('host_path') == vol2.get('host_path'):
                            dependencies.append({
                                'to_container_id': other_container.id,
                                'type': DependencyType.VOLUME,
                                'is_critical': False,
                                'detection_method': 'shared_volume',
                                'confidence_score': 80,
                                'description': f"Shares volume: {vol1.get('host_path')}"
                            })

        return dependencies

    async def _analyze_compose_file(
        self,
        container: Container,
        all_containers: List[Container]
    ) -> List[Dict]:
        """Analyze docker-compose file for explicit dependencies"""
        dependencies = []

        try:
            if not container.compose_file_path or not Path(container.compose_file_path).exists():
                return dependencies

            with open(container.compose_file_path, 'r') as f:
                compose_data = yaml.safe_load(f)

            if not compose_data or 'services' not in compose_data:
                return dependencies

            # Find this container's service
            service_name = container.compose_service_name
            if not service_name or service_name not in compose_data['services']:
                return dependencies

            service = compose_data['services'][service_name]

            # Check depends_on
            if 'depends_on' in service:
                depends_on = service['depends_on']
                if isinstance(depends_on, list):
                    dep_services = depends_on
                elif isinstance(depends_on, dict):
                    dep_services = list(depends_on.keys())
                else:
                    dep_services = []

                # Find containers for these services
                for dep_service in dep_services:
                    for other_container in all_containers:
                        if other_container.compose_service_name == dep_service:
                            dep_type = self._infer_dependency_from_services(container, other_container)

                            dependencies.append({
                                'to_container_id': other_container.id,
                                'type': dep_type or DependencyType.OTHER,
                                'is_critical': True,
                                'detection_method': 'docker_compose',
                                'confidence_score': 100,
                                'description': f"Explicit dependency in docker-compose.yml"
                            })

        except Exception as e:
            logger.error(f"Error analyzing compose file for {container.container_name}: {str(e)}")

        return dependencies

    def _detect_service_patterns(
        self,
        container: Container,
        all_containers: List[Container]
    ) -> List[Dict]:
        """Detect dependencies based on common service patterns"""
        dependencies = []

        container_name = container.container_name.lower()
        container_image = container.image.lower()

        for other_container in all_containers:
            if other_container.id == container.id:
                continue

            other_name = other_container.container_name.lower()
            other_image = other_container.image.lower()

            # Pattern: Service depends on database
            if self._is_database(other_image, other_name):
                if not self._is_database(container_image, container_name):
                    dependencies.append({
                        'to_container_id': other_container.id,
                        'type': DependencyType.DATABASE,
                        'is_critical': True,
                        'detection_method': 'pattern_matching',
                        'confidence_score': 60,
                        'description': f"Likely database dependency"
                    })

            # Pattern: Service depends on cache
            if self._is_cache(other_image, other_name):
                if not self._is_infrastructure(container_image, container_name):
                    dependencies.append({
                        'to_container_id': other_container.id,
                        'type': DependencyType.CACHE,
                        'is_critical': False,
                        'detection_method': 'pattern_matching',
                        'confidence_score': 50,
                        'description': f"Likely cache dependency"
                    })

            # Pattern: Service behind reverse proxy
            if self._is_reverse_proxy(other_image, other_name):
                if not self._is_infrastructure(container_image, container_name):
                    dependencies.append({
                        'to_container_id': other_container.id,
                        'type': DependencyType.REVERSE_PROXY,
                        'is_critical': False,
                        'detection_method': 'pattern_matching',
                        'confidence_score': 40,
                        'description': f"Service may be behind reverse proxy"
                    })

        return dependencies

    def _determine_dependency_type(self, env_key: str, env_value: str, target_container: Container) -> DependencyType:
        """Determine dependency type from environment variable"""
        key_lower = env_key.lower()
        value_lower = env_value.lower()
        image_lower = target_container.image.lower()

        if any(db in key_lower for db in ['database', 'db_', 'postgres', 'mysql', 'mongo', 'redis']):
            return DependencyType.DATABASE
        elif any(cache in key_lower for cache in ['cache', 'redis', 'memcached']):
            return DependencyType.CACHE
        elif any(mq in key_lower for mq in ['rabbitmq', 'kafka', 'nats', 'amqp']):
            return DependencyType.MESSAGE_QUEUE
        elif 'api' in key_lower or 'service' in key_lower:
            return DependencyType.API
        else:
            return DependencyType.OTHER

    def _infer_dependency_from_services(self, from_container: Container, to_container: Container) -> Optional[DependencyType]:
        """Infer dependency type from service types"""
        to_image = to_container.image.lower()
        to_name = to_container.container_name.lower()

        if self._is_database(to_image, to_name):
            return DependencyType.DATABASE
        elif self._is_cache(to_image, to_name):
            return DependencyType.CACHE
        elif self._is_message_queue(to_image, to_name):
            return DependencyType.MESSAGE_QUEUE
        elif self._is_reverse_proxy(to_image, to_name):
            return DependencyType.REVERSE_PROXY

        return None

    def _is_database(self, image: str, name: str) -> bool:
        """Check if service is a database"""
        patterns = ['postgres', 'mysql', 'mariadb', 'mongodb', 'mongo', 'redis', 'elasticsearch', 'influxdb']
        return any(p in image or p in name for p in patterns)

    def _is_cache(self, image: str, name: str) -> bool:
        """Check if service is a cache"""
        patterns = ['redis', 'memcached', 'varnish']
        return any(p in image or p in name for p in patterns)

    def _is_message_queue(self, image: str, name: str) -> bool:
        """Check if service is a message queue"""
        patterns = ['rabbitmq', 'kafka', 'nats', 'activemq']
        return any(p in image or p in name for p in patterns)

    def _is_reverse_proxy(self, image: str, name: str) -> bool:
        """Check if service is a reverse proxy"""
        patterns = ['nginx', 'traefik', 'caddy', 'haproxy', 'envoy']
        return any(p in image or p in name for p in patterns)

    def _is_infrastructure(self, image: str, name: str) -> bool:
        """Check if service is infrastructure"""
        return (self._is_database(image, name) or
                self._is_cache(image, name) or
                self._is_message_queue(image, name) or
                self._is_reverse_proxy(image, name))

    async def get_dependency_graph(self, session: AsyncSession, server_id: Optional[str] = None) -> Dict:
        """Get dependency graph for visualization"""
        query = select(Container)
        if server_id:
            query = query.where(Container.server_id == server_id)

        result = await session.execute(query)
        containers = result.scalars().all()

        nodes = []
        edges = []

        for container in containers:
            nodes.append({
                'id': container.id,
                'name': container.container_name,
                'image': container.image,
                'is_critical': container.is_critical,
                'type': self._classify_container(container)
            })

            # Get dependencies
            deps_result = await session.execute(
                select(ServiceDependency).where(
                    ServiceDependency.from_container_id == container.id
                )
            )
            dependencies = deps_result.scalars().all()

            for dep in dependencies:
                edges.append({
                    'from': container.id,
                    'to': dep.to_container_id,
                    'type': dep.dependency_type.value,
                    'is_critical': dep.is_critical,
                    'confidence': dep.confidence_score
                })

        return {
            'nodes': nodes,
            'edges': edges
        }

    def _classify_container(self, container: Container) -> str:
        """Classify container type"""
        image = container.image.lower()
        name = container.container_name.lower()

        if self._is_database(image, name):
            return 'database'
        elif self._is_cache(image, name):
            return 'cache'
        elif self._is_message_queue(image, name):
            return 'message_queue'
        elif self._is_reverse_proxy(image, name):
            return 'reverse_proxy'
        else:
            return 'application'

    async def get_update_order(self, session: AsyncSession, container_ids: List[str]) -> List[List[str]]:
        """Calculate update order based on dependencies (topological sort)"""
        # Build adjacency list
        graph = {cid: [] for cid in container_ids}
        in_degree = {cid: 0 for cid in container_ids}

        for cid in container_ids:
            deps_result = await session.execute(
                select(ServiceDependency).where(
                    ServiceDependency.from_container_id == cid,
                    ServiceDependency.to_container_id.in_(container_ids)
                )
            )
            dependencies = deps_result.scalars().all()

            for dep in dependencies:
                # from_container depends on to_container
                # So to_container must be updated first
                graph[dep.to_container_id].append(cid)
                in_degree[cid] += 1

        # Topological sort with levels (for parallel execution)
        result = []
        current_level = [cid for cid in container_ids if in_degree[cid] == 0]

        while current_level:
            result.append(current_level)
            next_level = []

            for cid in current_level:
                for dependent in graph[cid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level.append(dependent)

            current_level = next_level

        return result


# Global instance
dependency_service = DependencyService()
