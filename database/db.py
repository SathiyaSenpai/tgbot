"""
Senpai's Bot - Database Manager
Async SQLite database with WAL mode, memory-capped cache, and auto-migration.
"""
import aiosqlite
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Chat settings
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    chat_type TEXT,
    welcome_enabled INTEGER DEFAULT 1,
    welcome_text TEXT DEFAULT 'Welcome {mention} to {chatname}! 👋',
    goodbye_enabled INTEGER DEFAULT 0,
    goodbye_text TEXT DEFAULT 'Goodbye {first}! We will miss you.',
    clean_welcome INTEGER DEFAULT 0,
    clean_service INTEGER DEFAULT 0,
    last_welcome_msg_id INTEGER,
    rules_text TEXT,
    rules_private INTEGER DEFAULT 1,
    rules_button_text TEXT DEFAULT '📜 Read Rules',
    warn_limit INTEGER DEFAULT 3,
    warn_mode TEXT DEFAULT 'ban',
    flood_limit INTEGER DEFAULT 0,
    flood_mode TEXT DEFAULT 'mute',
    flood_time INTEGER DEFAULT 0,
    blocklist_mode TEXT DEFAULT 'delete',
    blocklist_delete INTEGER DEFAULT 1,
    blocklist_reason TEXT DEFAULT 'Blocklisted content detected.',
    reports_enabled INTEGER DEFAULT 1,
    log_channel_id INTEGER,
    captcha_enabled INTEGER DEFAULT 0,
    captcha_mode TEXT DEFAULT 'math',
    captcha_timeout INTEGER DEFAULT 300,
    captcha_kick INTEGER DEFAULT 1,
    captcha_text TEXT DEFAULT 'Please verify you are human.',
    clean_commands TEXT DEFAULT '',
    clean_messages TEXT DEFAULT '',
    private_notes INTEGER DEFAULT 0,
    disable_del INTEGER DEFAULT 0,
    antiraid INTEGER DEFAULT 0,
    antiraid_time INTEGER DEFAULT 21600,
    antiraid_action_time INTEGER DEFAULT 3600
);

-- User tracking
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warnings
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    warned_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_warnings_chat_user ON warnings(chat_id, user_id);

-- Notes
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    content TEXT,
    media_type TEXT,
    media_id TEXT,
    is_private INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    is_protected INTEGER DEFAULT 0,
    UNIQUE(chat_id, name)
);

-- Filters
CREATE TABLE IF NOT EXISTS filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    trigger_text TEXT NOT NULL,
    match_mode TEXT DEFAULT 'contains',
    response TEXT,
    media_type TEXT,
    media_id TEXT,
    UNIQUE(chat_id, trigger_text)
);

-- Blocklist
CREATE TABLE IF NOT EXISTS blocklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    trigger_text TEXT NOT NULL,
    reason TEXT,
    action TEXT,
    UNIQUE(chat_id, trigger_text)
);

-- Blocklisted users
CREATE TABLE IF NOT EXISTS blocklist_users (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    blocked_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(chat_id, user_id)
);

-- Disabled commands
CREATE TABLE IF NOT EXISTS disabled_commands (
    chat_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    PRIMARY KEY(chat_id, command)
);

-- Locks
CREATE TABLE IF NOT EXISTS locks (
    chat_id INTEGER NOT NULL,
    lock_type TEXT NOT NULL,
    PRIMARY KEY(chat_id, lock_type)
);

-- Approved users
CREATE TABLE IF NOT EXISTS approved_users (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    approved_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(chat_id, user_id)
);

-- Connections (PM ↔ Group)
CREATE TABLE IF NOT EXISTS connections (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL
);

-- Tracked repos (commit tracker)
CREATE TABLE IF NOT EXISTS tracked_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    branch TEXT DEFAULT 'main',
    added_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(owner, repo)
);

-- Repo cache (ETags, last SHA)
CREATE TABLE IF NOT EXISTS repo_cache (
    repo_id INTEGER PRIMARY KEY,
    last_sha TEXT,
    etag TEXT,
    last_modified TEXT,
    last_checked TIMESTAMP,
    last_security_patch TEXT,
    FOREIGN KEY(repo_id) REFERENCES tracked_repos(id) ON DELETE CASCADE
);

-- Commit subscribers
CREATE TABLE IF NOT EXISTS commit_subscribers (
    user_id INTEGER NOT NULL,
    repo_id INTEGER,
    PRIMARY KEY(user_id, repo_id)
);



-- Generic key-value store for bot state
CREATE TABLE IF NOT EXISTS bot_kv (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Scheduled messages
CREATE TABLE IF NOT EXISTS scheduled_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    job_id TEXT,
    sent INTEGER DEFAULT 0
);

-- Captcha pending verifications
CREATE TABLE IF NOT EXISTS captcha_pending (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    answer TEXT NOT NULL,
    message_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(chat_id, user_id)
);

-- Temp actions (temp bans, mutes for tracking expiry)
CREATE TABLE IF NOT EXISTS temp_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    job_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_temp_actions_expires ON temp_actions(expires_at);
"""


class Database:
    """Async SQLite database manager optimized for low memory usage."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        """Initialize database connection with memory-efficient PRAGMAs and create schema."""
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Memory-efficient PRAGMAs
        await self._conn.execute("PRAGMA journal_mode = WAL;")
        await self._conn.execute("PRAGMA synchronous = NORMAL;")
        await self._conn.execute("PRAGMA cache_size = -2000;")  # 2MB cap
        await self._conn.execute("PRAGMA busy_timeout = 5000;")
        await self._conn.execute("PRAGMA temp_store = MEMORY;")
        await self._conn.execute("PRAGMA mmap_size = 0;")  # Disable mmap on low RAM
        await self._conn.execute("PRAGMA foreign_keys = ON;")

        # Run schema creation
        await self._conn.executescript(SCHEMA_SQL)

        # Track schema version
        row = await self.fetchone("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        if row is None:
            await self.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            await self.commit()

        logger.info(f"Database initialized at {self.db_path}")

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a SQL query."""
        return await self._conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: list) -> aiosqlite.Cursor:
        """Execute a SQL query with multiple parameter sets."""
        return await self._conn.executemany(sql, params_list)

    async def commit(self) -> None:
        """Commit current transaction."""
        await self._conn.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetch a single row."""
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> List[aiosqlite.Row]:
        """Fetch all rows."""
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def fetchval(self, sql: str, params: tuple = (), default=None):
        """Fetch a single value from the first column of the first row."""
        row = await self.fetchone(sql, params)
        return row[0] if row else default

    # --- Chat helpers ---

    async def ensure_chat(self, chat_id: int, title: str = None, chat_type: str = None) -> None:
        """Ensure a chat exists in the database."""
        await self.execute(
            "INSERT INTO chats (chat_id, title, chat_type) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title = COALESCE(?, title), chat_type = COALESCE(?, chat_type)",
            (chat_id, title, chat_type, title, chat_type)
        )
        await self.commit()

    async def get_chat_setting(self, chat_id: int, setting: str, default=None):
        """Get a single chat setting value."""
        try:
            row = await self.fetchone(f"SELECT {setting} FROM chats WHERE chat_id = ?", (chat_id,))
            return row[0] if (row and row[0] is not None) else default
        except Exception as e:
            logger.debug(f"Failed to get setting {setting} for {chat_id}: {e}")
            return default

    async def set_chat_setting(self, chat_id: int, setting: str, value) -> None:
        """Set a single chat setting value."""
        await self.ensure_chat(chat_id)
        await self.execute(f"UPDATE chats SET {setting} = ? WHERE chat_id = ?", (value, chat_id))
        await self.commit()

    # --- User helpers ---

    async def ensure_user(self, user_id: int, username: str = None,
                          first_name: str = None, last_name: str = None) -> None:
        """Ensure a user exists in the database and update their info."""
        await self.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, last_seen) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "username = COALESCE(?, username), first_name = COALESCE(?, first_name), "
            "last_name = COALESCE(?, last_name), last_seen = CURRENT_TIMESTAMP",
            (user_id, username, first_name, last_name, username, first_name, last_name)
        )
        await self.commit()
