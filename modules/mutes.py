import logging
from datetime import datetime, timezone
from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import can_restrict, group_only
from utils.helpers import parse_time, get_target_user, mention_html, can_act_on_user

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

UNMUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=True,
    can_invite_users=True,
    can_pin_messages=True,
    can_manage_topics=True
)

@group_only
@can_restrict
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user to mute.")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("Cannot act on this user.")
        return
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS)
        text = f"Muted {mention_html(target_id, 'User')}."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Mute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to mute: {e}")

@group_only
@can_restrict
async def smute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
        
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        return
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS)
        await log_action(db, context, chat.id, f"<b>Silent Mute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except Exception:
        pass

@group_only
@can_restrict
async def dmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Reply to a message.")
        return
        
    target_id = update.effective_message.reply_to_message.from_user.id
    reason = " ".join(context.args) if context.args else ""
    
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("Cannot act on this user.")
        return
        
    try:
        await update.effective_message.reply_to_message.delete()
    except Exception:
        pass
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS)
        text = f"Muted {mention_html(target_id, 'User')} and deleted message."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>DMute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to mute: {e}")

@group_only
@can_restrict
async def tmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, rest = await get_target_user(update, context, return_rest=True)
    if not target_id or not rest:
        await update.effective_message.reply_text("Usage: /tmute <user> <time> [reason]")
        return
        
    parts = rest.split(maxsplit=1)
    time_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        await update.effective_message.reply_text("Invalid time format.")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("Cannot act on this user.")
        return
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS, until_date=until_date)
        text = f"Temp muted {mention_html(target_id, 'User')} until {until_date.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Temp Mute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to temp mute: {e}")

@group_only
@can_restrict
async def stmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
        
    target_id, rest = await get_target_user(update, context, return_rest=True)
    if not target_id or not rest:
        return
        
    parts = rest.split(maxsplit=1)
    time_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        return
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS, until_date=until_date)
        await log_action(db, context, chat.id, f"<b>Silent Temp Mute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except Exception:
        pass

@group_only
@can_restrict
async def dtmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Reply to a message.")
        return
        
    target_id = update.effective_message.reply_to_message.from_user.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /dtmute <time> [reason]")
        return
        
    time_str = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        await update.effective_message.reply_text("Invalid time format.")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("Cannot act on this user.")
        return
        
    try:
        await update.effective_message.reply_to_message.delete()
    except Exception:
        pass
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, MUTE_PERMISSIONS, until_date=until_date)
        text = f"Temp muted {mention_html(target_id, 'User')} and deleted message."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>D-Temp Mute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed: {e}")

@group_only
@can_restrict
async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user to unmute.")
        return
        
    try:
        await context.bot.restrict_chat_member(chat.id, target_id, UNMUTE_PERMISSIONS)
        await update.effective_message.reply_text(f"Unmuted {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Unmute</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to unmute: {e}")


def register(app):
    app.add_handler(CommandHandler("mute", mute_user), group=0)
    app.add_handler(CommandHandler("smute", smute_user), group=0)
    app.add_handler(CommandHandler("dmute", dmute_user), group=0)
    app.add_handler(CommandHandler("tmute", tmute_user), group=0)
    app.add_handler(CommandHandler("stmute", stmute_user), group=0)
    app.add_handler(CommandHandler("dtmute", dtmute_user), group=0)
    app.add_handler(CommandHandler("unmute", unmute_user), group=0)
