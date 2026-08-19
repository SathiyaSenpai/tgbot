import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes

from utils.decorators import admin_required, owner_required, can_restrict, group_only
from utils.helpers import get_target_user, mention_html, can_act_on_user

logger = logging.getLogger(__name__)

async def log_action(db, context, chat_id, text):
    log_channel_id = await db.get_chat_setting(chat_id, 'log_channel_id', None)
    if log_channel_id:
        try:
            await context.bot.send_message(chat_id=log_channel_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not send log to {log_channel_id}: {e}")

MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_manage_topics=False
)

async def punish_user(chat_id, target_id, bot, mode):
    try:
        if mode == "ban":
            await bot.ban_chat_member(chat_id, target_id, revoke_messages=True)
            return "Banned"
        elif mode == "kick":
            await bot.ban_chat_member(chat_id, target_id, revoke_messages=False)
            await bot.unban_chat_member(chat_id, target_id)
            return "Kicked"
        elif mode == "mute":
            await bot.restrict_chat_member(chat_id, target_id, MUTE_PERMISSIONS)
            return "Muted"
        elif mode == "tban":
            until_date = datetime.now(timezone.utc) + timedelta(days=1)
            await bot.ban_chat_member(chat_id, target_id, until_date=until_date, revoke_messages=True)
            return "Temp-banned (1 day)"
        elif mode == "tmute":
            until_date = datetime.now(timezone.utc) + timedelta(days=1)
            await bot.restrict_chat_member(chat_id, target_id, MUTE_PERMISSIONS, until_date=until_date)
            return "Temp-muted (1 day)"
    except Exception as e:
        logger.warning(f"Failed to punish user: {e}")
        return f"Failed to punish ({mode})"
    return "No action"

async def execute_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int, reason: str, silent: bool = False, delete_msg: bool = False):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        if not silent:
            await update.effective_message.reply_text("Cannot act on this user.")
        return
        
    limit_str = await db.get_chat_setting(chat.id, "warn_limit", "3")
    mode = await db.get_chat_setting(chat.id, "warn_mode", "ban")
    try:
        limit = int(limit_str)
    except:
        limit = 3
        
    if delete_msg and update.effective_message.reply_to_message:
        try:
            await update.effective_message.reply_to_message.delete()
        except:
            pass
            
    if silent:
        try:
            await update.effective_message.delete()
        except:
            pass

    await db.execute(
        "INSERT INTO warnings (chat_id, user_id, reason, warned_by) VALUES (?, ?, ?, ?)",
        (chat.id, target_id, reason, user.id)
    )
    await db.commit()
    
    count_val = await db.fetchval("SELECT COUNT(*) FROM warnings WHERE chat_id = ? AND user_id = ?", (chat.id, target_id))
    count = int(count_val) if count_val else 1
    
    action_taken = None
    if count >= limit:
        action_taken = await punish_user(chat.id, target_id, context.bot, mode)
        await db.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (chat.id, target_id))
        await db.commit()
        
    if not silent:
        text = f"Warned {mention_html(target_id, 'User')} ({count}/{limit})."
        if reason:
            text += f"\nReason: {reason}"
        if action_taken:
            text += f"\nLimit reached! Action: {action_taken}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        
    log_text = f"<b>Warning</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nCount: {count}/{limit}\nReason: {reason or 'None'}"
    if action_taken:
        log_text += f"\nAction: {action_taken}"
    await log_action(db, context, chat.id, log_text)

@group_only
@can_restrict
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
    await execute_warn(update, context, target_id, reason)

@group_only
@can_restrict
async def swarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        return
    await execute_warn(update, context, target_id, reason, silent=True)

@group_only
@can_restrict
async def dwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("You need to reply to a message, senpai! (´• ω •`)")
        return
    target_id = update.effective_message.reply_to_message.from_user.id
    reason = " ".join(context.args) if context.args else ""
    await execute_warn(update, context, target_id, reason, delete_msg=True)

@group_only
@can_restrict
async def warns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
        
    rows = await db.fetchall("SELECT id, reason, warned_by, created_at FROM warnings WHERE chat_id = ? AND user_id = ? ORDER BY id ASC", (chat.id, target_id))
    if not rows:
        await update.effective_message.reply_text("User has no warnings.")
        return
        
    limit = await db.get_chat_setting(chat.id, "warn_limit", "3")
    text = f"<b>Warnings for {mention_html(target_id, 'User')} ({len(rows)}/{limit}):</b>\n\n"
    for i, row in enumerate(rows, 1):
        reason = row[1] or "No reason"
        by = row[2]
        row[3]
        text += f"{i}. By <code>{by}</code>: {reason}\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
@can_restrict
async def rmwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
        
    row = await db.fetchone("SELECT id FROM warnings WHERE chat_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1", (chat.id, target_id))
    if not row:
        await update.effective_message.reply_text("No warnings to remove.")
        return
        
    await db.execute("DELETE FROM warnings WHERE id = ?", (row[0],))
    await db.commit()
    await update.effective_message.reply_text(f"Removed most recent warning for {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)

@group_only
@can_restrict
async def resetwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
        
    await db.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (chat.id, target_id))
    await db.commit()
    await update.effective_message.reply_text(f"Reset all warnings for {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)

@group_only
@owner_required
async def resetallwarns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    await db.execute("DELETE FROM warnings WHERE chat_id = ?", (chat.id,))
    await db.commit()
    await update.effective_message.reply_text("Reset all warnings for everyone in this chat.")

@group_only
@admin_required
async def warnlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    if not context.args:
        current = await db.get_chat_setting(chat.id, "warn_limit", "3")
        await update.effective_message.reply_text(f"Current warn limit: {current}")
        return
        
    try:
        limit = int(context.args[0])
        if limit < 1:
            raise ValueError
    except:
        await update.effective_message.reply_text("Provide a positive integer.")
        return
        
    await db.set_chat_setting(chat.id, "warn_limit", str(limit))
    await update.effective_message.reply_text(f"Warn limit set to {limit}.")

@group_only
@admin_required
async def warnmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    valid_modes = ["ban", "kick", "mute", "tban", "tmute"]
    if not context.args or context.args[0].lower() not in valid_modes:
        current = await db.get_chat_setting(chat.id, "warn_mode", "ban")
        await update.effective_message.reply_text(f"Current warn mode: {current}\nValid modes: {', '.join(valid_modes)}")
        return
        
    mode = context.args[0].lower()
    await db.set_chat_setting(chat.id, "warn_mode", mode)
    await update.effective_message.reply_text(f"Warn mode set to {mode}.")

def register(app):
    app.add_handler(CommandHandler("warn", warn_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "warn", warn_user), group=0)
    app.add_handler(CommandHandler("swarn", swarn_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "swarn", swarn_user), group=0)
    app.add_handler(CommandHandler("dwarn", dwarn_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "dwarn", dwarn_user), group=0)
    app.add_handler(CommandHandler("warns", warns_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "warns", warns_cmd), group=0)
    app.add_handler(CommandHandler("rmwarn", rmwarn_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "rmwarn", rmwarn_cmd), group=0)
    app.add_handler(CommandHandler("resetwarn", resetwarn_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "resetwarn", resetwarn_cmd), group=0)
    app.add_handler(CommandHandler("resetallwarns", resetallwarns_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "resetallwarns", resetallwarns_cmd), group=0)
    app.add_handler(CommandHandler("warnlimit", warnlimit_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "warnlimit", warnlimit_cmd), group=0)
    app.add_handler(CommandHandler("warnmode", warnmode_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "warnmode", warnmode_cmd), group=0)
