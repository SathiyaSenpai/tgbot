"""
Senpai's Bot - Chat Rules (Persistent AI Instructions)
Detects and stores per-group learning instructions from users with no extra API calls.
Rules are injected into the system prompt — zero cost on free tier.
"""
import logging
import re
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, PrefixHandler, filters, ContextTypes
from telegram.constants import ChatType, ParseMode

from utils.decorators import admin_required

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
# Patterns that signal a user is giving Scarlet an instruction
# All detection is done locally (no LLM call)
# ─────────────────────────────────────────────────────
_INSTRUCTION_PATTERNS = [
    # "don't / dont / do not / stop / never" + action
    r"(?:don[\'']?t|do not|stop|never|please don[\'']?t|please stop)\s+(.+)",
    # "always / always be / always use"
    r"(?:always|make sure you|you should|you must|from now on|remember to)\s+(.+)",
    # "only speak / only reply in"
    r"(?:only speak|only use|only reply in|speak only in|respond only in)\s+(.+)",
    # "i want you to" style
    r"(?:i want you to|i need you to|please)\s+(.+)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INSTRUCTION_PATTERNS]

# In-memory rule cache to avoid DB reads every single message
# { chat_id: ["rule 1", "rule 2", ...] }
_rule_cache: dict[int, list[str]] = {}
_MAX_RULES_PER_CHAT = 15  # cap to keep system prompt tight

MAX_RULE_LENGTH = 120  # Characters — keeps prompt compact


def register(app):
    app.add_handler(CommandHandler("rules", show_rules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "rules", show_rules), group=0)
    app.add_handler(CommandHandler("clearrules", clear_rules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "clearrules", clear_rules), group=0)
    app.add_handler(CommandHandler("delrule", delete_rule), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "delrule", delete_rule), group=0)
    # Listen to all text messages to detect instructions (low group number = before ai_chat)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, detect_instruction),
        group=4,
    )


def detect_instruction_in_text(text: str) -> str | None:
    """
    Local regex detection — no API call.
    Returns a clean instruction string if detected, else None.
    """
    for pattern in _COMPILED:
        m = pattern.match(text.strip())
        if m:
            raw = m.group(1).strip(" .,!?")
            # Must be meaningful (at least 5 chars, not too long)
            if 5 <= len(raw) <= MAX_RULE_LENGTH:
                return raw
    return None


async def _load_rules(chat_id: int, db) -> list[str]:
    """Load active rules for a chat from DB (cached in memory)."""
    if chat_id in _rule_cache:
        return _rule_cache[chat_id]
    rows = await db.fetchall(
        "SELECT rule FROM chat_rules WHERE chat_id = ? AND active = 1 ORDER BY id",
        (chat_id,),
    )
    rules = [r[0] for r in rows]
    _rule_cache[chat_id] = rules
    return rules


def _invalidate_cache(chat_id: int):
    _rule_cache.pop(chat_id, None)


async def get_rules_for_prompt(chat_id: int, db) -> str:
    """
    Return a compact rules block to inject into the system prompt.
    Called by ai_engine before each generation — no API cost, pure DB read.
    """
    rules = await _load_rules(chat_id, db)
    if not rules:
        return ""
    lines = "\n".join(f"- {r}" for r in rules)
    return f"\n\nSPECIAL RULES FOR THIS CHAT (you MUST follow these):\n{lines}"


async def detect_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Passively scan messages directed at the bot for instructions.
    Only triggers if the message looks like an instruction to Scarlet.
    ZERO extra API calls.
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return

    bot_id = context.bot.id
    bot_username = (context.bot.username or "").lower()
    chat_type = update.effective_chat.type

    # Only intercept if message is directed at bot
    is_private = chat_type == ChatType.PRIVATE
    is_mentioned = bot_username and f"@{bot_username}" in msg.text.lower()
    is_replied_to = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == bot_id
    )
    is_name_called = "scarlet" in msg.text.lower()

    if not (is_private or is_mentioned or is_replied_to or is_name_called):
        return

    # Strip the bot's name/mention before checking for instruction
    clean_text = re.sub(rf"@?{re.escape(bot_username)}", "", msg.text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\bscarlet\b", "", clean_text, flags=re.IGNORECASE).strip()

    instruction = detect_instruction_in_text(clean_text)
    if not instruction:
        return

    db = context.bot_data.get("db")
    if not db:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    rules = await _load_rules(chat_id, db)
    if len(rules) >= _MAX_RULES_PER_CHAT:
        logger.debug(f"[Chat Rules] Rule limit reached for chat {chat_id}. Not adding more.")
        return

    # Avoid exact duplicates
    if instruction.lower() in [r.lower() for r in rules]:
        return

    await db.execute(
        "INSERT INTO chat_rules (chat_id, rule, added_by) VALUES (?, ?, ?)",
        (chat_id, instruction, user_id),
    )
    await db.commit()
    _invalidate_cache(chat_id)

    logger.info(f"[Chat Rules] Saved rule for chat {chat_id}: '{instruction}'")


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all active rules for this chat."""
    db = context.bot_data.get("db")
    if not db:
        return

    chat_id = update.effective_chat.id
    rows = await db.fetchall(
        "SELECT id, rule, added_at FROM chat_rules WHERE chat_id = ? AND active = 1 ORDER BY id",
        (chat_id,),
    )

    if not rows:
        await update.effective_message.reply_text("No custom rules saved for this chat yet.")
        return

    text = "📋 <b>Scarlet's Rules for This Chat</b>\n\n"
    for r in rows:
        text += f"• <code>#{r[0]}</code> {r[1]}\n"
    text += "\n<i>Use /delrule &lt;id&gt; to remove one, or /clearrules to wipe all.</i>"

    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@admin_required
async def delete_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a specific rule by ID."""
    if not context.args:
        await update.effective_message.reply_text("Usage: /delrule &lt;id&gt;", parse_mode=ParseMode.HTML)
        return

    try:
        rule_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid ID.")
        return

    db = context.bot_data.get("db")
    chat_id = update.effective_chat.id

    row = await db.fetchone(
        "SELECT id FROM chat_rules WHERE id = ? AND chat_id = ? AND active = 1",
        (rule_id, chat_id),
    )
    if not row:
        await update.effective_message.reply_text(f"No active rule with ID #{rule_id} in this chat.")
        return

    await db.execute("UPDATE chat_rules SET active = 0 WHERE id = ?", (rule_id,))
    await db.commit()
    _invalidate_cache(chat_id)

    await update.effective_message.reply_text(f"✅ Rule <code>#{rule_id}</code> removed.", parse_mode=ParseMode.HTML)

@admin_required
async def clear_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipe all rules for this chat (admin only by convention)."""
    db = context.bot_data.get("db")
    chat_id = update.effective_chat.id

    await db.execute("UPDATE chat_rules SET active = 0 WHERE chat_id = ?", (chat_id,))
    await db.commit()
    _invalidate_cache(chat_id)

    await update.effective_message.reply_text("✅ All custom rules cleared for this chat.")
