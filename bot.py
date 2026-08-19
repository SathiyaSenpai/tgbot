#!/usr/bin/env python3
"""
Senpai's Bot - Main Entry Point
Telegram bot combining ROM commit tracking with group management.

Optimized for low-memory servers (1 GiB RAM).
"""
import gc
import sys
import logging
from pathlib import Path

# Use uvloop for faster event loop (Linux only)
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

from telegram.ext import ApplicationBuilder, Application

from config import BOT_TOKEN, LOG_LEVEL, DB_PATH, GITHUB_TOKEN, validate_config
from database.db import Database
from utils.github_client import GitHubClient
from modules import register_all_handlers

logging.basicConfig(
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
# Reduce noise from httpx and apscheduler
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._updater").setLevel(logging.WARNING)

logger = logging.getLogger("senpai")


async def post_init(application: Application) -> None:
    logger.info("Initializing Senpai's Bot...")

    db = Database(DB_PATH)
    await db.init()
    application.bot_data["db"] = db

    github = GitHubClient(token=GITHUB_TOKEN)
    await github.init()
    application.bot_data["github"] = github

    me = await application.bot.get_me()
    logger.info(f"Bot: @{me.username} ({me.first_name}) [ID: {me.id}]")
    logger.info("Senpai's Bot initialized successfully! ✅")


async def post_shutdown(application: Application) -> None:
    logger.info("Shutting down Senpai's Bot...")

    db = application.bot_data.get("db")
    if db:
        await db.close()

    github = application.bot_data.get("github")
    if github:
        await github.close()

    logger.info("Senpai's Bot shutdown complete.")


def main():
    validate_config()

    # Aggressive garbage collection for low-memory servers
    gc.set_threshold(400, 5, 5)

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    logger.info("Building application...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    register_all_handlers(app)

    logger.info("Starting polling...")
    app.run_polling(
        drop_pending_updates=True,
        poll_interval=1.0,
        allowed_updates=[
            "message",
            "edited_message",
            "callback_query",
            "chat_member",
            "my_chat_member",
        ],
    )


if __name__ == "__main__":
    main()
