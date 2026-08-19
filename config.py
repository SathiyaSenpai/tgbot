"""
Senpai's Bot - Configuration
Loads environment variables from .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Your Telegram user ID (superadmin). Get it by messaging @userinfobot
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Personal Access Token for higher rate limits (5000/hr vs 60/hr)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# How often to poll GitHub for new commits (in minutes)
COMMIT_POLL_INTERVAL = int(os.getenv("COMMIT_POLL_INTERVAL", "5"))

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "data" / "bot.db"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

ENABLE_COMMIT_TRACKER = os.getenv("ENABLE_COMMIT_TRACKER", "true").lower() == "true"
ENABLE_GROUP_MANAGEMENT = os.getenv("ENABLE_GROUP_MANAGEMENT", "true").lower() == "true"


def validate_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set. Get it from @BotFather on Telegram")
    if OWNER_ID == 0:
        errors.append("OWNER_ID is not set. Get your Telegram user ID from @userinfobot")
    if errors:
        for error in errors:
            print(f"❌ CONFIG ERROR: {error}")
        print("\nPlease set these values in your .env file.")
        raise SystemExit(1)
