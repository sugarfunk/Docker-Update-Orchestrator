import httpx
import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class ChangelogService:
    """Service for retrieving changelogs from various sources"""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Docker-Update-Orchestrator/1.0"}
        )

    async def get_changelog(self, image_name: str, from_version: str,
                           to_version: str, github_repo: Optional[str] = None) -> Optional[Dict]:
        """
        Get changelog for an image version update
        Returns: {
            "source": "github|dockerhub|website",
            "url": "...",
            "raw_changelog": "...",
            "format": "markdown|html|plain"
        }
        """
        try:
            # Try multiple sources
            changelog = None

            # 1. Try GitHub releases if repo is known
            if github_repo:
                changelog = await self._get_github_changelog(github_repo, from_version, to_version)
                if changelog:
                    return changelog

            # 2. Try finding GitHub repo from image name
            if not github_repo:
                github_repo = await self._find_github_repo(image_name)
                if github_repo:
                    changelog = await self._get_github_changelog(github_repo, from_version, to_version)
                    if changelog:
                        return changelog

            # 3. Try Docker Hub
            changelog = await self._get_dockerhub_changelog(image_name, to_version)
            if changelog:
                return changelog

            # 4. Try common changelog URLs
            changelog = await self._try_common_changelog_urls(image_name, github_repo)
            if changelog:
                return changelog

            return None

        except Exception as e:
            logger.error(f"Error getting changelog for {image_name}: {str(e)}")
            return None

    async def _get_github_changelog(self, github_repo: str, from_version: str,
                                    to_version: str) -> Optional[Dict]:
        """Get changelog from GitHub releases"""
        try:
            # Clean version tags
            from_tag = self._clean_version_tag(from_version)
            to_tag = self._clean_version_tag(to_version)

            # Try getting release notes
            url = f"https://api.github.com/repos/{github_repo}/releases/tags/{to_tag}"
            response = await self.client.get(url)

            if response.status_code == 200:
                release = response.json()
                return {
                    "source": "github_release",
                    "url": release.get("html_url"),
                    "raw_changelog": release.get("body", ""),
                    "format": "markdown",
                    "release_name": release.get("name"),
                    "published_at": release.get("published_at"),
                    "author": release.get("author", {}).get("login")
                }

            # Try compare view
            compare_url = f"https://github.com/{github_repo}/compare/{from_tag}...{to_tag}"
            response = await self.client.get(compare_url)

            if response.status_code == 200:
                # Parse commits from compare page
                soup = BeautifulSoup(response.text, "html.parser")
                commits = []

                for commit in soup.select(".commit-message"):
                    commits.append(commit.get_text(strip=True))

                if commits:
                    changelog_text = "\n".join(f"- {commit}" for commit in commits[:50])
                    return {
                        "source": "github_compare",
                        "url": compare_url,
                        "raw_changelog": changelog_text,
                        "format": "plain",
                        "commit_count": len(commits)
                    }

            # Try CHANGELOG.md file
            changelog_url = f"https://raw.githubusercontent.com/{github_repo}/main/CHANGELOG.md"
            response = await self.client.get(changelog_url)

            if response.status_code == 200:
                changelog_text = response.text
                # Extract relevant section for this version
                relevant_section = self._extract_version_section(changelog_text, to_version)

                return {
                    "source": "github_changelog_file",
                    "url": f"https://github.com/{github_repo}/blob/main/CHANGELOG.md",
                    "raw_changelog": relevant_section or changelog_text[:5000],
                    "format": "markdown"
                }

            return None

        except Exception as e:
            logger.error(f"Error getting GitHub changelog for {github_repo}: {str(e)}")
            return None

    async def _get_dockerhub_changelog(self, image_name: str, version: str) -> Optional[Dict]:
        """Get changelog from Docker Hub"""
        try:
            # Docker Hub API
            url = f"https://hub.docker.com/v2/repositories/{image_name}"
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                description = data.get("full_description", "")

                if description:
                    return {
                        "source": "dockerhub",
                        "url": f"https://hub.docker.com/r/{image_name}",
                        "raw_changelog": description,
                        "format": "markdown"
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting Docker Hub changelog for {image_name}: {str(e)}")
            return None

    async def _try_common_changelog_urls(self, image_name: str,
                                        github_repo: Optional[str]) -> Optional[Dict]:
        """Try common changelog URL patterns"""
        urls_to_try = []

        if github_repo:
            base = f"https://raw.githubusercontent.com/{github_repo}/main"
            urls_to_try.extend([
                f"{base}/CHANGELOG.md",
                f"{base}/CHANGELOG",
                f"{base}/CHANGES.md",
                f"{base}/CHANGES",
                f"{base}/HISTORY.md",
                f"{base}/RELEASES.md",
                f"{base}/docs/CHANGELOG.md",
                f"{base}/docs/changelog.md"
            ])

        for url in urls_to_try:
            try:
                response = await self.client.get(url)
                if response.status_code == 200:
                    return {
                        "source": "changelog_file",
                        "url": url.replace("raw.githubusercontent.com", "github.com").replace("/main/", "/blob/main/"),
                        "raw_changelog": response.text[:10000],
                        "format": "markdown"
                    }
            except:
                continue

        return None

    async def _find_github_repo(self, image_name: str) -> Optional[str]:
        """Try to find GitHub repository for an image"""
        try:
            # Try Docker Hub API
            url = f"https://hub.docker.com/v2/repositories/{image_name}"
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()

                # Check source URL
                source_url = data.get("source_url", "")
                if "github.com" in source_url:
                    return self._extract_github_repo(source_url)

                # Check description for GitHub links
                description = data.get("full_description", "")
                github_match = re.search(r"github\.com/([^/\s]+/[^/\s]+)", description)
                if github_match:
                    return github_match.group(1).rstrip("/")

            return None

        except Exception as e:
            logger.error(f"Error finding GitHub repo for {image_name}: {str(e)}")
            return None

    def _extract_github_repo(self, url: str) -> Optional[str]:
        """Extract GitHub repo from URL"""
        match = re.search(r"github\.com/([^/]+/[^/\s]+)", url)
        if match:
            repo = match.group(1).rstrip("/")
            # Remove .git suffix if present
            repo = repo.replace(".git", "")
            return repo
        return None

    def _clean_version_tag(self, version: str) -> str:
        """Clean version string to match common tag formats"""
        # Try with 'v' prefix
        if not version.startswith("v") and not version.startswith("V"):
            return f"v{version}"
        return version

    def _extract_version_section(self, changelog: str, version: str) -> Optional[str]:
        """Extract the section for a specific version from changelog"""
        try:
            # Try different version formats
            version_patterns = [
                version,
                f"v{version}",
                f"V{version}",
                version.lstrip("v").lstrip("V")
            ]

            for pattern in version_patterns:
                # Look for markdown headers with version
                regex = rf"#+\s*\[?{re.escape(pattern)}\]?.*?\n(.*?)(?=\n#+\s|\Z)"
                match = re.search(regex, changelog, re.DOTALL | re.IGNORECASE)

                if match:
                    return match.group(0)

            return None

        except Exception as e:
            logger.error(f"Error extracting version section: {str(e)}")
            return None

    async def get_release_notes_batch(self, github_repo: str, versions: List[str]) -> Dict[str, Optional[Dict]]:
        """Get release notes for multiple versions in batch"""
        results = {}

        for version in versions:
            try:
                tag = self._clean_version_tag(version)
                url = f"https://api.github.com/repos/{github_repo}/releases/tags/{tag}"
                response = await self.client.get(url)

                if response.status_code == 200:
                    release = response.json()
                    results[version] = {
                        "body": release.get("body", ""),
                        "url": release.get("html_url"),
                        "published_at": release.get("published_at"),
                        "name": release.get("name")
                    }
                else:
                    results[version] = None

            except Exception as e:
                logger.error(f"Error getting release notes for {version}: {str(e)}")
                results[version] = None

        return results

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global instance
changelog_service = ChangelogService()
