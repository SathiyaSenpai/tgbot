import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# Dictionary to store flood counts: {(chat_id, user_id): count}
flood_counts = defaultdict(int)
# Dictionary to store last sender: {chat_id: user_id}
last_senders = {}

def register(app):
    app.add_handler(CommandHandler("flood", flood_status), group=0)
    app.add_handler(CommandHandler("setflood", setflood), group=0)
    app.add_handler(CommandHandler("setfloodmode", setfloodmode), group=0)
    
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, check_flood), group=-1)

@group_only
@admin_required
async def flood_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    flood_limit = await db.get_chat_setting(chat_id, "flood_limit", 0)
    flood_mode = await db.get_chat_setting(chat_id, "flood_mode", "mute")
    
    if flood_limit > 0:
        await update.effective_message.reply_text(
            f"<b>Antiflood Settings</b>\nLimit: {flood_limit} messages\nAction: {flood_mode}",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_message.reply_text("Antiflood is currently disabled.")

@group_only
@admin_required
async def setflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setflood <N|off>")
        return
        
    arg = context.args[0].lower()
    
    if arg == "off":
        limit = 0
    elif arg.isdigit():
        limit = int(arg)
    else:
        await update.effective_message.reply_text("Usage: /setflood <N|off>")
        return
        
    await db.set_chat_setting(chat_id, "flood_limit", limit)
    await db.commit()
    
    if limit == 0:
        await update.effective_message.reply_text("Antiflood disabled.")
    else:
        await update.effective_message.reply_text(f"Antiflood limit set to {limit} consecutive messages.")

@group_only
@admin_required
async def setfloodmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setfloodmode <ban|kick|mute|tban|tmute>")
        return
        
    mode = context.args[0].lower()
    valid_modes = ["ban", "kick", "mute", "tban", "tmute"]
    
    if mode not in valid_modes:
        await update.effective_message.reply_text(f"Invalid mode. Valid modes are: {', '.join(valid_modes)}")
        return
        
    await db.set_chat_setting(chat_id, "flood_mode", mode)
    await db.commit()
    
    await update.effective_message.reply_text(f"Antiflood action set to: {mode}")

async def is_admin_or_approved(chat_id, user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return True
        # Could also check for approved/whitelisted users in DB here
        return False
    except TelegramError:
        return False

async def check_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.effective_message
        if not msg:
            return
            
        user = update.effective_user
        if not user or user.is_bot:
            return
            
        chat = update.effective_chat
        if not chat:
            return
            
        db = context.bot_data.get("db")
        if not db:
            return
            
        flood_limit = await db.get_chat_setting(chat.id, "flood_limit", 0)
        
        if not flood_limit or flood_limit <= 0:
            return
            
        if await is_admin_or_approved(chat.id, user.id, context.bot):
            return
            
        last_sender = last_senders.get(chat.id)
        
        if last_sender != user.id:
            last_senders[chat.id] = user.id
            flood_counts[(chat.id, user.id)] = 1
            return
            
        flood_counts[(chat.id, user.id)] += 1
        
        if flood_counts[(chat.id, user.id)] > flood_limit:
            flood_mode = await db.get_chat_setting(chat.id, "flood_mode", "mute")
            
            try:
                if flood_mode == "ban":
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await msg.reply_text(f"User {user.first_name} was banned for flooding.")
                elif flood_mode == "kick":
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await context.bot.unban_chat_member(chat.id, user.id)
                    await msg.reply_text(f"User {user.first_name} was kicked for flooding.")
                elif flood_mode == "mute":
                    from telegram import ChatPermissions
                    await context.bot.restrict_chat_member(
                        chat.id, 
                        user.id, 
                        ChatPermissions(can_send_messages=False)
                    )
                    await msg.reply_text(f"User {user.first_name} was muted for flooding.")
                
                # Reset counter after action
                flood_counts[(chat.id, user.id)] = 0
                
            except (TelegramError, BadRequest, Forbidden) as e:
                logger.warning(f"Could not apply flood action: {e}")
    except Exception as e:
        logger.debug(f"Error in check_flood: {e}")
