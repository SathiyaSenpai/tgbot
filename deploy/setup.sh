#!/usr/bin/env bash
# Senpai's Bot - Server Setup Script
# Run as root on a fresh Ubuntu/Debian server
set -euo pipefail

echo "========================================="
echo "  Senpai's Bot - Server Setup"
echo "========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BOT_DIR="/opt/senpais-bot"
BOT_USER="senpai"

# --- Step 1: System packages ---
echo -e "${YELLOW}[1/7] Installing system packages...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip libjemalloc2 zram-tools git > /dev/null 2>&1
echo -e "${GREEN}✓ System packages installed${NC}"

# --- Step 2: Configure zram swap for better memory utilization ---
echo -e "${YELLOW}[2/7] Configuring zram swap...${NC}"
if ! grep -q "PERCENTAGE=50" /etc/default/zramswap 2>/dev/null; then
    cat > /etc/default/zramswap << 'EOF'
ALGO=zstd
PERCENTAGE=50
PRIORITY=100
EOF
    systemctl restart zramswap
fi
echo -e "${GREEN}✓ zram swap configured (50% = ~512MB compressed swap)${NC}"

# --- Step 3: Create bot user ---
echo -e "${YELLOW}[3/7] Creating bot user...${NC}"
if ! id "$BOT_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$BOT_DIR" "$BOT_USER"
fi
echo -e "${GREEN}✓ User '$BOT_USER' ready${NC}"

# --- Step 4: Deploy bot files ---
echo -e "${YELLOW}[4/7] Deploying bot files...${NC}"
mkdir -p "$BOT_DIR/data"

# Copy bot files (assumes this script is run from the project directory)
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cp -r "$SCRIPT_DIR"/*.py "$BOT_DIR/"
cp -r "$SCRIPT_DIR"/database "$BOT_DIR/"
cp -r "$SCRIPT_DIR"/utils "$BOT_DIR/"
cp -r "$SCRIPT_DIR"/modules "$BOT_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$BOT_DIR/"

# Copy .env if it doesn't exist yet
if [ ! -f "$BOT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$BOT_DIR/.env"
    echo -e "${RED}⚠ IMPORTANT: Edit $BOT_DIR/.env with your bot token and settings!${NC}"
fi

chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
echo -e "${GREEN}✓ Bot files deployed to $BOT_DIR${NC}"

# --- Step 5: Create Python virtual environment ---
echo -e "${YELLOW}[5/7] Setting up Python virtual environment...${NC}"
if [ ! -d "$BOT_DIR/venv" ]; then
    python3 -m venv "$BOT_DIR/venv"
fi
"$BOT_DIR/venv/bin/pip" install --quiet --upgrade pip
"$BOT_DIR/venv/bin/pip" install --quiet -r "$BOT_DIR/requirements.txt"
chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR/venv"
echo -e "${GREEN}✓ Python environment ready${NC}"

# --- Step 6: Install systemd service ---
echo -e "${YELLOW}[6/7] Installing systemd service...${NC}"
cp "$SCRIPT_DIR/deploy/senpais-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable senpais-bot
echo -e "${GREEN}✓ Systemd service installed and enabled${NC}"

# --- Step 7: Final instructions ---
echo ""
echo "========================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit the config file:"
echo "     sudo nano $BOT_DIR/.env"
echo ""
echo "  2. Set your BOT_TOKEN (from @BotFather)"
echo "     Set your OWNER_ID (from @userinfobot)"
echo "     Set your GITHUB_TOKEN (optional, for commit tracking)"
echo ""
echo "  3. Start the bot:"
echo "     sudo systemctl start senpais-bot"
echo ""
echo "  4. Check status:"
echo "     sudo systemctl status senpais-bot"
echo "     sudo journalctl -u senpais-bot -f"
echo ""
echo "  5. Add the bot to your Telegram group as admin"
echo "     with ALL permissions enabled"
echo ""
