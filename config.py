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

# ── AI Provider Keys ──────────────────────────────────────────────────────────
# At least ONE of the three providers must be set for chat to work.
# Get Gemini key: https://aistudio.google.com  (1,500 req/day free)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Get Groq key: https://console.groq.com       (1,000+ req/day free, very fast)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Get OpenRouter key: https://openrouter.ai    (50+ req/day free, 300+ models)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── GIF Support ───────────────────────────────────────────────────────────────
# Optional. Get a free Tenor API key: https://developers.google.com/tenor/guides/quickstart
# Without this, GIFs are disabled (bot still works fine).
TENOR_API_KEY = os.getenv("TENOR_API_KEY", "")

# How often to poll GitHub for new commits (in minutes)
COMMIT_POLL_INTERVAL = int(os.getenv("COMMIT_POLL_INTERVAL", "5"))

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent / "data" / "bot.db"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

ENABLE_COMMIT_TRACKER = os.getenv("ENABLE_COMMIT_TRACKER", "true").lower() == "true"
ENABLE_GROUP_MANAGEMENT = os.getenv("ENABLE_GROUP_MANAGEMENT", "true").lower() == "true"


def validate_config():
    errors = []
    warnings = []

    # Hard requirements — bot cannot function without these
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set. Get it from @BotFather on Telegram.")
    if OWNER_ID == 0:
        errors.append("OWNER_ID is not set. Get your Telegram user ID from @userinfobot.")

    # Soft requirements — bot works in degraded mode without these
    if not any([GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY]):
        errors.append(
            "No AI provider key is set. Set at least one of: GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY."
        )
    else:
        active = []
        if GEMINI_API_KEY:
            active.append("Gemini")
        if GROQ_API_KEY:
            active.append("Groq")
        if OPENROUTER_API_KEY:
            active.append("OpenRouter")
        print(f"✓ AI providers enabled: {', '.join(active)}")

    if not TENOR_API_KEY:
        warnings.append("TENOR_API_KEY not set — GIF sending disabled (optional).")

    if warnings:
        for w in warnings:
            print(f"⚠️  WARNING: {w}")

    if errors:
        for error in errors:
            print(f"❌ CONFIG ERROR: {error}")
        print("\nPlease set these values in your .env file.")
        raise SystemExit(1)
