#!/usr/bin/env bash
# Senpai's Bot - Safe Server Update Script
# Updates code files without touching the live database (data/) or secrets (.env)
set -euo pipefail

BOT_DIR="/opt/senpais-bot"
BOT_USER="senpai"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================="
echo "  Senpai's Bot - Safe Update"
echo "========================================="

# 1. Sync code files while strictly preserving data/ and .env
echo "Syncing code files..."
rsync -av \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'data' \
  --exclude '.env' \
  --exclude '.git' \
  --exclude '__pycache__' \
  "$SCRIPT_DIR/" "$BOT_DIR/"

# 2. Set ownership and permissions
chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
chmod 750 "$BOT_DIR"
chmod 770 "$BOT_DIR/data"

# 3. Update python dependencies if virtualenv exists
if [ -f "$BOT_DIR/venv/bin/pip" ]; then
    echo "Updating dependencies..."
    "$BOT_DIR/venv/bin/pip" install --quiet -r "$BOT_DIR/requirements.txt"
fi

# 4. Restart service
echo "Restarting service..."
systemctl restart senpais-bot

echo "========================================="
echo "✓ Update complete! Database and notes preserved."
echo "========================================="
