"""
Senpai's Bot - GitHub API Client
Async client for polling commits with ETag caching.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


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
        # Fast path: raw.githubusercontent.com (no rate limits)
        try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            headers = {"User-Agent": "SenpaisBot/1.0"}
            if self.token:
                headers["Authorization"] = f"token {self.token}"
            response = await self._client.get(raw_url, headers=headers)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.debug(f"raw.githubusercontent failed for {owner}/{repo}/{path}: {e}")

        # Fallback to standard API endpoint
        try:
            response = await self._client.get(
                f"/repos/{owner}/{repo}/contents/{path}",
                params={"ref": branch},
                headers={"Accept": "application/vnd.github.v3.raw"},
            )
            if response.status_code == 200:
                return response.text
            logger.debug(f"[{owner}/{repo}] File {path} not found: {response.status_code}")
            return None
        except Exception as e:
            logger.debug(f"[{owner}/{repo}] Failed to get file {path}: {e}")
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
        message = commit_data.get("message", "No message").split("\n")[0]
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
