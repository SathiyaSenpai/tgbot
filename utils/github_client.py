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

    async def check_asb(self, org: str, branch: str) -> Optional[str]:
        """Fetch the security patch level for a ROM org.
        
        Tries these sources in order:
        1. LineageOS Gerrit REST API (for LineageOS org - gets real-time merged security patches)
        2. android_build_release flag_values on GitHub
        3. core/build_id.mk date parsing (for crDroid and others)
        4. Legacy version_defaults.mk
        """
        # 1. LineageOS Gerrit REST API
        if org.lower() == "lineageos":
            try:
                # Query for specific branch or general latest security bump
                query = f"project:LineageOS/android_build_release+status:merged+message:\"Bump Security String\"+branch:{branch}"
                gerrit_url = f"https://review.lineageos.org/changes/?q={query}&n=3"
                resp = await self._client.get(gerrit_url)
                if resp.status_code == 200:
                    text = resp.text
                    if text.startswith(")]}'"):
                        text = text[4:].strip()
                    import json
                    changes = json.loads(text)
                    for c in changes:
                        match = re.search(r"(\d{4}-\d{2}-\d{2})", c.get("subject", ""))
                        if match:
                            return match.group(1)
            except Exception as e:
                logger.debug(f"Gerrit check failed for {org}/{branch}: {e}")

        # 2. Figure out the build tag prefix from the BUILD_ID
        build_id = await self.get_file_content(org, "android_build", "core/build_id.mk", branch)
        tag = None
        if build_id:
            for line in build_id.splitlines():
                if line.startswith("BUILD_ID="):
                    tag = line.split("=", 1)[1].strip().split(".")[0].lower()
                    break

        # Try the release flag file first (LineageOS GitHub)
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

        # 3. Fallback: parse date from BUILD_ID itself (e.g. BP1A.250505.005 -> 2025-05-05)
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

        # 4. Legacy fallback: version_defaults.mk
        content = await self.get_file_content(org, "android_build", "core/version_defaults.mk", branch)
        if content:
            match = SECURITY_PATCH_REGEX.search(content)
            if match:
                return match.group(1)

        return None

    async def fetch_device_tree_updates(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch latest merged commits for SM8650, avalon, and audi trees from LineageOS Gerrit."""
        try:
            query = "(project:LineageOS/android_device_oneplus_avalon+OR+project:LineageOS/android_device_oneplus_audi+OR+project:LineageOS/android_device_oneplus_sm8650-common)+status:merged"
            url = f"https://review.lineageos.org/changes/?q={query}&n={limit}"
            resp = await self._client.get(url)
            if resp.status_code == 200:
                text = resp.text
                if text.startswith(")]}'"):
                    text = text[4:].strip()
                import json
                data = json.loads(text)
                results = []
                for c in data:
                    proj = c.get("project", "").split("/")[-1]
                    results.append({
                        "id": c.get("id"),
                        "repo": proj,
                        "branch": c.get("branch"),
                        "subject": c.get("subject"),
                        "updated": c.get("updated", "")[:10],
                        "number": c.get("_number"),
                    })
                return results
        except Exception as e:
            logger.debug(f"Failed to fetch device tree updates from Gerrit: {e}")
        return []

    async def fetch_gerrit_security_bumps(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch latest merged security bumps across all branches from LineageOS Gerrit."""
        try:
            query = "project:LineageOS/android_build_release+status:merged+message:\"Bump Security String\""
            url = f"https://review.lineageos.org/changes/?q={query}&n={limit}"
            resp = await self._client.get(url)
            if resp.status_code == 200:
                text = resp.text
                if text.startswith(")]}'"):
                    text = text[4:].strip()
                import json
                data = json.loads(text)
                results = []
                for c in data:
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", c.get("subject", ""))
                    if m:
                        results.append({
                            "patch_date": m.group(1),
                            "branch": c.get("branch"),
                            "subject": c.get("subject"),
                            "updated": c.get("updated", "")[:10],
                        })
                return results
        except Exception as e:
            logger.debug(f"Failed to fetch Gerrit security bumps: {e}")
        return []

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
