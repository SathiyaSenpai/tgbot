"""
Senpai's Bot - GitHub API Client
Async client for polling commits with ETag caching.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

SECURITY_PATCH_REGEX = re.compile(r"PLATFORM_SECURITY_PATCH\s*:=\s*(\d{4}-\d{2}-\d{2})")


class GitHubClient:

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = ""):
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def init(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "SenpaisBot/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )
        logger.info("GitHub API client initialized" + (" (authenticated)" if self.token else " (unauthenticated)"))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_commits(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        since: Optional[str] = None,
        etag: Optional[str] = None,
        per_page: int = 10,
    ) -> Dict[str, Any]:
        params = {"sha": branch, "per_page": per_page}
        if since:
            params["since"] = since

        headers = {}
        if etag:
            headers["If-None-Match"] = etag

        try:
            response = await self._client.get(
                f"/repos/{owner}/{repo}/commits",
                params=params,
                headers=headers,
            )

            result = {
                "status": response.status_code,
                "commits": [],
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "rate_remaining": int(response.headers.get("x-ratelimit-remaining", -1)),
            }

            if response.status_code == 304:
                logger.debug(f"[{owner}/{repo}] No changes (304)")
                return result

            if response.status_code == 200:
                result["commits"] = response.json()
                logger.info(
                    f"[{owner}/{repo}] {len(result['commits'])} commits. "
                    f"Rate remaining: {result['rate_remaining']}"
                )
                return result

            logger.warning(f"[{owner}/{repo}] API error {response.status_code}: {response.text[:200]}")
            return result

        except httpx.TimeoutException:
            logger.error(f"[{owner}/{repo}] Request timeout")
            return {"status": 0, "commits": [], "etag": etag, "last_modified": None, "rate_remaining": -1}
        except Exception as e:
            logger.error(f"[{owner}/{repo}] Request failed: {e}")
            return {"status": 0, "commits": [], "etag": etag, "last_modified": None, "rate_remaining": -1}

    async def get_file_content(
        self, owner: str, repo: str, path: str, branch: str = "main"
    ) -> Optional[str]:
        try:
            response = await self._client.get(
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": branch},
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            if response.status_code == 200:
                return response.text
            logger.warning(f"[{owner}/{repo}] File {path} not found: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[{owner}/{repo}] Failed to get file {path}: {e}")
            return None

    async def check_asb(self, org: str, branch: str) -> Optional[str]:
        """Fetch the security patch level for a ROM org.
        
        Tries these sources in order:
        1. android_build_release flag_values (LineageOS)
        2. core/build_id.mk date parsing (crDroid and others)
        """
        # Figure out the build tag prefix from the BUILD_ID
        build_id = await self.get_file_content(org, "android_build", "core/build_id.mk", branch)
        tag = None
        if build_id:
            for line in build_id.splitlines():
                if line.startswith("BUILD_ID="):
                    tag = line.split("=", 1)[1].strip().split(".")[0].lower()
                    break

        # Try the release flag file first (LineageOS style)
        if tag:
            content = await self.get_file_content(
                org, "android_build_release",
                f"flag_values/{tag}/RELEASE_PLATFORM_SECURITY_PATCH.textproto",
                branch,
            )
            if content:
                match = re.search(r'string_value:\s*"(\d{4}-\d{2}-\d{2})"', content)
                if match:
                    return match.group(1)

        # Fallback: parse date from BUILD_ID itself (e.g. BP1A.250505.005 -> 2025-05-05)
        if build_id:
            for line in build_id.splitlines():
                if line.startswith("BUILD_ID="):
                    bid = line.split("=", 1)[1].strip()
                    parts = bid.split(".")
                    if len(parts) >= 2 and len(parts[1]) == 6:
                        try:
                            raw = parts[1]
                            year = 2000 + int(raw[:2])
                            month = int(raw[2:4])
                            day = int(raw[4:6])
                            return f"{year}-{month:02d}-{day:02d}"
                        except ValueError:
                            pass
                    break

        # Legacy fallback: version_defaults.mk
        content = await self.get_file_content(org, "android_build", "core/version_defaults.mk", branch)
        if content:
            match = SECURITY_PATCH_REGEX.search(content)
            if match:
                return match.group(1)

        return None

    async def get_rate_limit(self) -> Dict[str, Any]:
        try:
            response = await self._client.get("/rate_limit")
            if response.status_code == 200:
                data = response.json()
                core = data.get("resources", {}).get("core", {})
                return {
                    "limit": core.get("limit", 0),
                    "remaining": core.get("remaining", 0),
                    "reset": datetime.fromtimestamp(
                        core.get("reset", 0), tz=timezone.utc
                    ).isoformat(),
                }
        except Exception as e:
            logger.error(f"Failed to get rate limit: {e}")
        return {"limit": 0, "remaining": 0, "reset": "unknown"}

    def format_commit(self, commit: dict) -> str:
        sha = commit.get("sha", "")[:7]
        commit_data = commit.get("commit", {})
        message = commit_data.get("message", "No message").split("\n")[0]  # First line only
        author_data = commit_data.get("author", {})
        author_name = author_data.get("name", "Unknown")
        url = commit.get("html_url", "")

        files = commit.get("files", [])
        file_count = len(files) if files else ""
        file_info = f"\n📁 {file_count} file(s) changed" if file_count else ""

        return (
            f"📝 <code>{sha}</code> — {_escape_html(message)}\n"
            f"👤 {_escape_html(author_name)}"
            f"{file_info}\n"
            f"🔗 <a href=\"{url}\">View commit</a>"
        )


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
