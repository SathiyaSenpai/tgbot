import logging
import re
import shlex
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.error import TelegramError

from utils.decorators import admin_required, owner_required, is_user_admin, group_only
from utils.helpers import mention_html

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("addblocklist", add_blocklist), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "addblocklist", add_blocklist), group=0)
    app.add_handler(CommandHandler("rmblocklist", rm_blocklist), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "rmblocklist", rm_blocklist), group=0)
    app.add_handler(CommandHandler("blocklist", list_blocklist), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "blocklist", list_blocklist), group=0)
    app.add_handler(CommandHandler("unblocklistall", unblocklist_all), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "unblocklistall", unblocklist_all), group=0)
    app.add_handler(CommandHandler("blocklistmode", set_blocklist_mode), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "blocklistmode", set_blocklist_mode), group=0)
    app.add_handler(CommandHandler("blocklistdelete", set_blocklist_delete), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "blocklistdelete", set_blocklist_delete), group=0)
    app.add_handler(CommandHandler("setblocklistreason", set_blocklist_reason), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setblocklistreason", set_blocklist_reason), group=0)
    app.add_handler(CommandHandler("resetblocklistreason", reset_blocklist_reason), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "resetblocklistreason", reset_blocklist_reason), group=0)
    
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, blocklist_scanner), 
        group=1
    )

@group_only
@admin_required
async def add_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /addblocklist <trigger> [reason] [{action}]", parse_mode=ParseMode.HTML)
        return
        
    args_str = " ".join(context.args)
    try:
        parsed_args = shlex.split(args_str)
    except ValueError:
        parsed_args = context.args
        
    if not parsed_args:
        return
        
    trigger = parsed_args[0].lower()
    
    action = None
    reason = None
    
    if len(parsed_args) > 1:
        last_arg = parsed_args[-1]
        if last_arg.startswith("{") and last_arg.endswith("}"):
            action = last_arg[1:-1].lower()
            if action not in ["nothing", "warn", "kick", "ban", "mute", "tban", "tmute"]:
                await update.effective_message.reply_text("Invalid action. Use {nothing|warn|kick|ban|mute|tban|tmute}.", parse_mode=ParseMode.HTML)
                return
            if len(parsed_args) > 2:
                reason = " ".join(parsed_args[1:-1])
        else:
            reason = " ".join(parsed_args[1:])
            
    await db.execute(
        "INSERT INTO blocklist (chat_id, trigger_text, reason, action) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, trigger_text) DO UPDATE SET reason=excluded.reason, action=excluded.action",
        (chat_id, trigger, reason, action)
    )
    await db.commit()
    
    msg = f"Added <b>{trigger}</b> to blocklist."
    if action:
        msg += f"\nAction: {action}"
    if reason:
        msg += f"\nReason: {reason}"
        
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def rm_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /rmblocklist <trigger>", parse_mode=ParseMode.HTML)
        return
        
    args_str = " ".join(context.args)
    try:
        parsed_args = shlex.split(args_str)
        trigger = parsed_args[0].lower()
    except ValueError:
        trigger = context.args[0].lower()
        
    row = await db.execute("DELETE FROM blocklist WHERE chat_id = ? AND trigger_text = ?", (chat_id, trigger))
    await db.commit()
    
    if row.rowcount > 0:
        await update.effective_message.reply_text(f"Removed <b>{trigger}</b> from blocklist.", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"<b>{trigger}</b> not found in blocklist.", parse_mode=ParseMode.HTML)

@group_only
async def list_blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT trigger_text, action FROM blocklist WHERE chat_id = ?", (chat_id,))
    
    if not rows:
        await update.effective_message.reply_text("No blocklist triggers set in this chat.", parse_mode=ParseMode.HTML)
        return
        
    text = "<b>Blocklist triggers:</b>\n"
    for row in rows:
        trigger = row["trigger_text"]
        action = row["action"]
        act_str = f" [{action}]" if action else ""
        text += f"- <code>{trigger}</code>{act_str}\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@owner_required
async def unblocklist_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("DELETE FROM blocklist WHERE chat_id = ?", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Cleared all blocklist triggers for this chat.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def set_blocklist_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /blocklistmode <nothing|warn|kick|ban|mute|tban|tmute>", parse_mode=ParseMode.HTML)
        return
        
    mode = context.args[0].lower()
    if mode not in ["nothing", "warn", "kick", "ban", "mute", "tban", "tmute"]:
        await update.effective_message.reply_text("Invalid mode. Use nothing, warn, kick, ban, mute, tban, tmute.", parse_mode=ParseMode.HTML)
        return
        
    await db.set_chat_setting(chat_id, "blocklist_mode", mode)
    await db.commit()
    
    await update.effective_message.reply_text(f"Blocklist default action set to: <b>{mode}</b>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def set_blocklist_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /blocklistdelete <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower()
    if val in ["on", "yes", "true"]:
        await db.set_chat_setting(chat_id, "blocklist_delete", "1")
    elif val in ["off", "no", "false"]:
        await db.set_chat_setting(chat_id, "blocklist_delete", "0")
    else:
        await update.effective_message.reply_text("Invalid value. Use on or off.", parse_mode=ParseMode.HTML)
        return
        
    await db.commit()
    await update.effective_message.reply_text(f"Blocklist message deletion set to: <b>{val}</b>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def set_blocklist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setblocklistreason <reason>", parse_mode=ParseMode.HTML)
        return
        
    reason = " ".join(context.args)
    await db.set_chat_setting(chat_id, "blocklist_reason", reason)
    await db.commit()
    
    await update.effective_message.reply_text(f"Blocklist default reason set to: <b>{reason}</b>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def reset_blocklist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("UPDATE chat_settings SET setting_value = NULL WHERE chat_id = ? AND setting_name = 'blocklist_reason'", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Blocklist default reason reset.", parse_mode=ParseMode.HTML)

async def blocklist_scanner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
        
    chat = update.effective_chat
    user = update.effective_user
    if not user or user.is_bot or not chat:
        return
        
    db = context.bot_data.get("db")
    if not db:
        return
        
    if await is_user_admin(chat.id, user.id, context, update):
        return
        
    approved = await db.fetchval("SELECT 1 FROM approved_users WHERE chat_id = ? AND user_id = ?", (chat.id, user.id))
    if approved:
        return
        
    text = update.effective_message.text.lower()
    
    triggers = await db.fetchall("SELECT trigger_text, reason, action FROM blocklist WHERE chat_id = ?", (chat.id,))
    if not triggers:
        return
        
    for trigger_row in triggers:
        trigger = trigger_row["trigger_text"].lower()
        trigger_re = re.compile(rf'\b{re.escape(trigger)}\b', re.IGNORECASE)
        
        if trigger_re.search(text):
            action = trigger_row["action"]
            if not action:
                action = await db.get_chat_setting(chat.id, "blocklist_mode", "nothing")
                
            reason = trigger_row["reason"]
            if not reason:
                reason = await db.get_chat_setting(chat.id, "blocklist_reason", "Triggered blocklist")
                
            del_mode = await db.get_chat_setting(chat.id, "blocklist_delete", "1")
            if del_mode == "1":
                try:
                    await update.effective_message.delete()
                except TelegramError as e:
                    logger.error(f"Failed to delete blocklist message: {e}")
                    
            user_link = mention_html(user.id, user.first_name)
            
            try:
                if action == "ban":
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await context.bot.send_message(chat.id, f"{user_link} was banned.\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "kick":
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await context.bot.unban_chat_member(chat.id, user.id)
                    await context.bot.send_message(chat.id, f"{user_link} was kicked.\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "mute":
                    await context.bot.restrict_chat_member(chat.id, user.id, permissions=context.bot_data.get("mute_permissions"))
                    await context.bot.send_message(chat.id, f"{user_link} was muted.\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "tban":
                    until = datetime.now() + timedelta(days=1)
                    await context.bot.ban_chat_member(chat.id, user.id, until_date=until)
                    await context.bot.send_message(chat.id, f"{user_link} was temporarily banned (1 day).\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "tmute":
                    until = datetime.now() + timedelta(days=1)
                    await context.bot.restrict_chat_member(chat.id, user.id, permissions=context.bot_data.get("mute_permissions"), until_date=until)
                    await context.bot.send_message(chat.id, f"{user_link} was temporarily muted (1 day).\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "warn":
                    await context.bot.send_message(chat.id, f"{user_link} was warned.\nReason: {reason}", parse_mode=ParseMode.HTML)
                elif action == "nothing":
                    pass
            except TelegramError as e:
                logger.error(f"Failed to apply blocklist action {action}: {e}")
            break
