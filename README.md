# Senpai's Bot 🤖

A Telegram group management bot with ROM commit tracking, built for low-memory servers.

**Features:** Ban/kick/mute (with silent & delete variants), warnings, blocklist, filters, notes, rules (with PM redirect), welcome/goodbye, CAPTCHA, pins, purge, antiflood, locks, approvals, reports, log channel, scheduled messages, auto-delete, command control, PM remote admin, GitHub commit tracker with security patch detection, and bot identity management.

## Quick Start

### 1. Get Your Credentials

1. **Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token
2. **Your User ID**: Message [@userinfobot](https://t.me/userinfobot) → copy your numeric ID
3. **GitHub PAT** *(optional)*: [github.com/settings/tokens](https://github.com/settings/tokens) → create read-only token for public repos

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Set at minimum:
```
BOT_TOKEN=123456:ABC-DEF...
OWNER_ID=your_numeric_id
```

### 3. Install & Run (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 4. Deploy to Server (Production)

```bash
# On your Azure VM (run as root):
sudo bash deploy/setup.sh

# Edit config:
sudo nano /opt/senpais-bot/.env

# Start:
sudo systemctl start senpais-bot
sudo systemctl status senpais-bot

# View logs:
sudo journalctl -u senpais-bot -f
```

### 5. Add Bot to Group

1. Add your bot to your Telegram group
2. Promote it to **admin** with ALL permissions
3. Send `/help` in the group

---

## Command Reference

### 👑 Admin
| Command | Description |
|---------|-------------|
| `/ban` `/sban` `/dban` `/tban` | Ban (silent/delete/temp variants) |
| `/unban` | Unban user |
| `/kick` `/skick` `/dkick` | Kick user |
| `/promote <user> [title]` | Promote to admin |
| `/demote` | Remove admin rights |
| `/adminlist` | List admins |
| `/settitle <user> <title>` | Set admin title |

### 🔇 Mute
| Command | Description |
|---------|-------------|
| `/mute` `/smute` `/dmute` `/tmute` | Mute (silent/delete/temp) |
| `/unmute` | Unmute user |

### ⚠️ Warnings
| Command | Description |
|---------|-------------|
| `/warn` `/dwarn` `/swarn` | Warn user |
| `/warns <user>` | Check warnings |
| `/rmwarn` `/resetwarn` | Remove warnings |
| `/warnlimit <N>` | Set max warnings (default: 3) |
| `/warnmode <ban\|kick\|mute>` | Set punishment |

### 🚫 Blocklist
| Command | Description |
|---------|-------------|
| `/addblocklist <trigger>` | Add blocked word/phrase |
| `/rmblocklist <trigger>` | Remove trigger |
| `/blocklist` | List all |
| `/blocklistmode <action>` | Set action (delete/warn/ban/kick/mute) |

### 🔍 Filters
| Command | Description |
|---------|-------------|
| `/filter <trigger> <response>` | Auto-respond to keyword |
| `/filters` | List filters |
| `/stop <trigger>` | Remove filter |

### 📝 Notes
| Command | Description |
|---------|-------------|
| `/save <name> <content>` | Save note |
| `/get <name>` or `#name` | Retrieve note |
| `/notes` | List all |
| `/privatenotes <on\|off>` | Send via PM |

### 👋 Greetings
| Command | Description |
|---------|-------------|
| `/setwelcome <text>` | Set welcome message |
| `/welcome <on\|off>` | Toggle |
| `/setgoodbye <text>` | Set goodbye |
| `/cleanwelcome <on\|off>` | Clean old welcomes |
| `/cleanservice <on\|off>` | Clean join/leave notifications |

**Fillings:** `{first}` `{last}` `{fullname}` `{username}` `{mention}` `{id}` `{chatname}` `{count}` `{rules}`

**Buttons:** `[Button Text](buttonurl://https://example.com)` (`:same` for same line)

### 📜 Rules
| Command | Description |
|---------|-------------|
| `/rules` | View rules (sends PM button) |
| `/setrules <text>` | Set rules |
| `/privaterules <on\|off>` | Toggle PM redirect |

### 🤖 CAPTCHA
| Command | Description |
|---------|-------------|
| `/captcha <on\|off>` | Toggle verification |
| `/captchamode <math\|button>` | Set challenge type |
| `/captchatime <5m>` | Set timeout |
| `/captchakick <on\|off>` | Kick on fail |

### 📡 Commit Tracker
| Command | Description |
|---------|-------------|
| `/addrepo LineageOS/android_device_oneplus_avalon lineage-22.1` | Track repo |
| `/rmrepo LineageOS/android_device_oneplus_avalon` | Untrack |
| `/repos` | List tracked repos |
| `/setbranch <owner/repo> <branch>` | Change branch |
| `/trackme` | Subscribe to notifications |
| `/untrackme` | Unsubscribe |
| `/commits <owner/repo>` | Manual check |
| `/checkasb` | Check security patch level |

### Other
| Command | Description |
|---------|-------------|
| `/lock <type>` `/unlock <type>` | Lock/unlock content types |
| `/approve <user>` | Trusted user (bypasses restrictions) |
| `/report` (reply) | Report to admins |
| `/connect` | Remote admin from PM |
| `/disable <cmd>` `/enable <cmd>` | Disable/enable commands |
| `/schedule <5m> <msg>` | Schedule message |
| `/setlog` | Set audit log channel |
| `/setbotname <name>` | Change bot name (owner) |
| `/setbotphoto` (reply to image) | Change bot photo (owner) |
| `/pin` `/unpin` `/purge` `/del` | Pin/purge management |
| `/kickme` `/bam <user>` | Fun commands |

---

## Memory Usage

| Component | RAM |
|-----------|-----|
| Linux OS + systemd + SSH | ~150 MB |
| Bot (Python + PTB + SQLite) | ~55–80 MB |
| **Remaining for Tailscale + other** | **~770+ MB** |

Optimizations applied:
- `jemalloc` memory allocator via `LD_PRELOAD`
- `uvloop` C-based event loop
- `zram` compressed swap (512 MB effective)
- SQLite WAL mode with 2 MB cache cap
- Aggressive GC tuning

---

## Project Structure

```
senpais-bot/
├── bot.py              # Entry point
├── config.py           # Environment config
├── .env.example        # Config template
├── requirements.txt    # Dependencies
├── database/
│   └── db.py           # SQLite + schema
├── utils/
│   ├── decorators.py   # Permission checks
│   ├── helpers.py      # Time parsing, user resolution
│   ├── formatting.py   # Template fillings engine
│   └── github_client.py # GitHub API with ETags
├── modules/            # 24 feature modules
│   ├── admin.py, mutes.py, warnings.py
│   ├── blocklist.py, filters.py, notes.py
│   ├── greetings.py, rules.py, captcha.py
│   ├── pins.py, purge.py, antiflood.py
│   ├── locks.py, reports.py, approvals.py
│   ├── connection.py, commandcontrol.py
│   ├── logchannel.py, commits.py
│   ├── scheduled.py, autodelete.py
│   ├── botsettings.py, misc.py
│   └── start.py        # Help + deep-link router
└── deploy/
    ├── setup.sh        # One-command server setup
    └── senpais-bot.service # Systemd unit
```

## License

MIT
