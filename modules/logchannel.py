import logging
import re
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

from utils.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

async def log_action(context, chat_id, action_text):
    db = context.bot_data.get('db')
    if not db:
        return
    log_channel = await db.get_chat_setting(chat_id, 'log_channel_id', None)
    if log_channel:
        try:
            await context.bot.send_message(log_channel, action_text, parse_mode='HTML')
        except TelegramError as e:
            logger.warning(f"Failed to log to channel {log_channel}: {e}")

async def setlog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type != ChatType.CHANNEL:
        await update.effective_message.reply_text("This command must be used in a channel.", parse_mode=ParseMode.HTML)
        return
        
    try:
        admins = await chat.get_administrators()
        admin_ids = [a.user.id for a in admins]
        if update.effective_user.id not in admin_ids:
            return # Silent fail if not admin in channel
    except TelegramError:
        return
        
    await update.effective_message.reply_text(
        f"To set this channel as a log channel, forward this message to the target group.\n\n"
        f"#SETLOG_CHANNEL_{chat.id}",
        parse_mode=ParseMode.HTML
    )

@group_only
@admin_required
async def forward_setlog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.forward_from_chat or msg.forward_from_chat.type != ChatType.CHANNEL:
        return
        
    text = msg.text or ""
    match = re.search(r'#SETLOG_CHANNEL_(-?\d+)', text)
    if not match:
        return
        
    channel_id_str = match.group(1)
    try:
        channel_id = int(channel_id_str)
    except ValueError:
        return
        
    if msg.forward_from_chat.id != channel_id:
        return
        
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        if bot_member.status != 'administrator'or not bot_member.can_post_messages:
            await msg.reply_text("I need to be an admin with post rights in that channel first.", parse_mode=ParseMode.HTML)
            return
    except TelegramError:
        await msg.reply_text("I cannot access that channel. Am I an admin there?", parse_mode=ParseMode.HTML)
        return
        
    await db.set_chat_setting(chat_id, 'log_channel_id', channel_id)
    await db.commit()
    
    await msg.reply_text(f"Log channel successfully linked to <b>{msg.forward_from_chat.title}</b>.", parse_mode=ParseMode.HTML)
    
@group_only
@admin_required
async def logchannel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    log_channel = await db.get_chat_setting(chat_id, 'log_channel_id', None)
    if not log_channel:
        await update.effective_message.reply_text("No log channel is set.", parse_mode=ParseMode.HTML)
        return
        
    try:
        channel = await context.bot.get_chat(log_channel)
        title = channel.title
    except TelegramError:
        title = "Unknown Channel"
        
    await update.effective_message.reply_text(f"Current log channel is <b>{title}</b> (<code>{log_channel}</code>).", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def unsetlog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.set_chat_setting(chat_id, 'log_channel_id', None)
    await db.commit()
    
    await update.effective_message.reply_text("Log channel unlinked.", parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("setlog", setlog_cmd), group=0)
    app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.GROUPS, forward_setlog_handler), group=0)
    app.add_handler(CommandHandler("logchannel", logchannel_cmd), group=0)
    app.add_handler(CommandHandler("unsetlog", unsetlog_cmd), group=0)
