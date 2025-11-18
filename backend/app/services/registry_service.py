import httpx
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import re
from packaging import version
import semver

logger = logging.getLogger(__name__)


class RegistryService:
    """Service for querying container registries for updates"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def check_for_updates(self, registry: str, repository: str,
                                current_tag: str) -> Optional[Dict]:
        """
        Check if updates are available for an image
        Returns update info or None
        """
        try:
            # Get available tags
            tags = await self.get_available_tags(registry, repository)
            if not tags:
                return None

            # Parse current version
            current_version = self._parse_version(current_tag)
            if not current_version:
                logger.warning(f"Could not parse version from tag: {current_tag}")
                return None

            # Find newer versions
            newer_versions = []
            for tag_info in tags:
                tag = tag_info["name"]
                tag_version = self._parse_version(tag)

                if tag_version and self._is_newer(tag_version, current_version):
                    newer_versions.append({
                        "tag": tag,
                        "version": tag_version,
                        "digest": tag_info.get("digest"),
                        "last_updated": tag_info.get("last_updated"),
                        "update_type": self._determine_update_type(current_version, tag_version)
                    })

            # Sort by version (newest first)
            newer_versions.sort(key=lambda x: x["version"], reverse=True)

            if newer_versions:
                latest = newer_versions[0]
                return {
                    "current_tag": current_tag,
                    "current_version": str(current_version),
                    "latest_tag": latest["tag"],
                    "latest_version": str(latest["version"]),
                    "latest_digest": latest.get("digest"),
                    "update_type": latest["update_type"],
                    "last_updated": latest.get("last_updated"),
                    "all_newer_versions": newer_versions,
                    "update_available": True
                }

            return {
                "current_tag": current_tag,
                "current_version": str(current_version),
                "update_available": False
            }

        except Exception as e:
            logger.error(f"Error checking updates for {registry}/{repository}:{current_tag}: {str(e)}")
            return None

    async def get_available_tags(self, registry: str, repository: str) -> List[Dict]:
        """Get all available tags for an image"""
        if registry == "docker.io":
            return await self._get_dockerhub_tags(repository)
        elif registry == "ghcr.io":
            return await self._get_ghcr_tags(repository)
        else:
            return await self._get_generic_registry_tags(registry, repository)

    async def _get_dockerhub_tags(self, repository: str) -> List[Dict]:
        """Get tags from Docker Hub"""
        try:
            url = f"https://hub.docker.com/v2/repositories/{repository}/tags"
            params = {"page_size": 100, "ordering": "last_updated"}

            all_tags = []
            while url:
                response = await self.client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                results = data.get("results", [])

                for tag_data in results:
                    all_tags.append({
                        "name": tag_data["name"],
                        "digest": tag_data.get("digest"),
                        "last_updated": tag_data.get("last_updated"),
                        "size": tag_data.get("full_size")
                    })

                url = data.get("next")
                if url and len(all_tags) >= 500:  # Limit to prevent too many requests
                    break

            return all_tags

        except Exception as e:
            logger.error(f"Error fetching Docker Hub tags for {repository}: {str(e)}")
            return []

    async def _get_ghcr_tags(self, repository: str) -> List[Dict]:
        """Get tags from GitHub Container Registry"""
        try:
            # GitHub Container Registry uses OCI distribution API
            url = f"https://ghcr.io/v2/{repository}/tags/list"

            response = await self.client.get(url)
            response.raise_for_status()

            data = response.json()
            tags = data.get("tags", [])

            result = []
            for tag in tags:
                # Get manifest for each tag to get digest and date
                manifest_url = f"https://ghcr.io/v2/{repository}/manifests/{tag}"
                try:
                    manifest_response = await self.client.get(
                        manifest_url,
                        headers={"Accept": "application/vnd.oci.image.index.v1+json"}
                    )
                    if manifest_response.status_code == 200:
                        digest = manifest_response.headers.get("Docker-Content-Digest")
                        result.append({
                            "name": tag,
                            "digest": digest
                        })
                except:
                    result.append({"name": tag})

            return result

        except Exception as e:
            logger.error(f"Error fetching GHCR tags for {repository}: {str(e)}")
            return []

    async def _get_generic_registry_tags(self, registry: str, repository: str) -> List[Dict]:
        """Get tags from generic Docker registry (OCI-compliant)"""
        try:
            url = f"https://{registry}/v2/{repository}/tags/list"

            response = await self.client.get(url)
            response.raise_for_status()

            data = response.json()
            tags = data.get("tags", [])

            return [{"name": tag} for tag in tags]

        except Exception as e:
            logger.error(f"Error fetching tags from {registry}/{repository}: {str(e)}")
            return []

    async def get_image_info(self, registry: str, repository: str, tag: str) -> Optional[Dict]:
        """Get detailed information about a specific image"""
        if registry == "docker.io":
            return await self._get_dockerhub_image_info(repository, tag)
        else:
            return await self._get_generic_image_info(registry, repository, tag)

    async def _get_dockerhub_image_info(self, repository: str, tag: str) -> Optional[Dict]:
        """Get image info from Docker Hub"""
        try:
            # Get tag info
            tag_url = f"https://hub.docker.com/v2/repositories/{repository}/tags/{tag}"
            response = await self.client.get(tag_url)
            response.raise_for_status()
            tag_data = response.json()

            # Get repository info
            repo_url = f"https://hub.docker.com/v2/repositories/{repository}"
            repo_response = await self.client.get(repo_url)
            repo_response.raise_for_status()
            repo_data = repo_response.json()

            return {
                "tag": tag,
                "digest": tag_data.get("digest"),
                "last_updated": tag_data.get("last_updated"),
                "size": tag_data.get("full_size"),
                "architecture": tag_data.get("images", [{}])[0].get("architecture"),
                "os": tag_data.get("images", [{}])[0].get("os"),
                "description": repo_data.get("description"),
                "star_count": repo_data.get("star_count"),
                "pull_count": repo_data.get("pull_count"),
                "is_official": repo_data.get("is_official", False),
                "is_automated": repo_data.get("is_automated", False)
            }

        except Exception as e:
            logger.error(f"Error fetching Docker Hub info for {repository}:{tag}: {str(e)}")
            return None

    async def _get_generic_image_info(self, registry: str, repository: str, tag: str) -> Optional[Dict]:
        """Get image info from generic registry"""
        try:
            # Get manifest
            manifest_url = f"https://{registry}/v2/{repository}/manifests/{tag}"
            response = await self.client.get(
                manifest_url,
                headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
            )
            response.raise_for_status()

            digest = response.headers.get("Docker-Content-Digest")
            manifest = response.json()

            return {
                "tag": tag,
                "digest": digest,
                "schema_version": manifest.get("schemaVersion"),
                "media_type": manifest.get("mediaType")
            }

        except Exception as e:
            logger.error(f"Error fetching info from {registry}/{repository}:{tag}: {str(e)}")
            return None

    async def find_github_repo(self, image_name: str) -> Optional[str]:
        """Try to find GitHub repository for an image"""
        try:
            # Try Docker Hub first
            if "/" not in image_name or image_name.startswith("library/"):
                repo = image_name.replace("library/", "")
                url = f"https://hub.docker.com/v2/repositories/library/{repo}"
            else:
                url = f"https://hub.docker.com/v2/repositories/{image_name}"

            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()

                # Check for GitHub link in description or source URL
                source_url = data.get("source_url")
                if source_url and "github.com" in source_url:
                    return self._extract_github_repo(source_url)

            return None

        except Exception as e:
            logger.error(f"Error finding GitHub repo for {image_name}: {str(e)}")
            return None

    def _extract_github_repo(self, url: str) -> Optional[str]:
        """Extract GitHub repo from URL"""
        match = re.search(r"github\.com/([^/]+/[^/]+)", url)
        if match:
            return match.group(1).rstrip("/")
        return None

    def _parse_version(self, tag: str) -> Optional[version.Version]:
        """Parse version from tag"""
        # Remove common prefixes
        tag = tag.lstrip("v").lstrip("V")

        # Try parsing as semantic version
        try:
            return version.parse(tag)
        except:
            pass

        # Try extracting version from tag like "1.2.3-alpine"
        match = re.match(r"^(\d+\.\d+\.?\d*)", tag)
        if match:
            try:
                return version.parse(match.group(1))
            except:
                pass

        return None

    def _is_newer(self, new_version: version.Version, current_version: version.Version) -> bool:
        """Check if new_version is newer than current_version"""
        return new_version > current_version

    def _determine_update_type(self, current: version.Version,
                               new: version.Version) -> str:
        """Determine update type (major, minor, patch)"""
        try:
            if hasattr(current, 'major') and hasattr(new, 'major'):
                if new.major > current.major:
                    return "major"
                elif new.minor > current.minor:
                    return "minor"
                elif new.micro > current.micro:
                    return "patch"
            return "unknown"
        except:
            return "unknown"

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global instance
registry_service = RegistryService()
