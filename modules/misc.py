import logging
import time
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

from utils.decorators import group_only
from utils.helpers import get_target_user

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("kickme", kickme), group=0)
    app.add_handler(CommandHandler("bam", bam), group=0)
    app.add_handler(CommandHandler("id", get_id), group=0)
    app.add_handler(CommandHandler("info", info), group=0)
    app.add_handler(CommandHandler("ping", ping), group=0)

@group_only
async def kickme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=user.id)
        await update.effective_message.reply_text(f"🚪 {user.first_name} has kicked themselves out of the chat.")
    except TelegramError as e:
        logger.error(f"Error in kickme: {e}")
        await update.effective_message.reply_text("I couldn't kick you. Make sure I have admin rights to restrict users.")

async def bam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, target_name = await get_target_user(update, context)
    
    if not target_id:
        await update.effective_message.reply_text("Please specify a user to bam.")
        return
        
    text = f"🔨 {target_name} has been bammed! (just kidding 😄)"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    
    text = ""
    if msg.reply_to_message:
        replied_user = msg.reply_to_message.from_user
        text += f"Replied User ID: <code>{replied_user.id}</code>\n"
        
    text += f"Your ID: <code>{update.effective_user.id}</code>\n"
    
    if update.effective_chat.type != ChatType.PRIVATE:
        text += f"Chat ID: <code>{update.effective_chat.id}</code>\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id, target_name = await get_target_user(update, context)
    
    if not target_id:
        target_id = update.effective_user.id
        
    try:
        user_info = await context.bot.get_chat(target_id)
        
        text = "👤 <b>User Info</b>\n"
        text += f"<b>ID:</b> <code>{user_info.id}</code>\n"
        text += f"<b>First Name:</b> {user_info.first_name}\n"
        
        if user_info.last_name:
            text += f"<b>Last Name:</b> {user_info.last_name}\n"
            
        if user_info.username:
            text += f"<b>Username:</b> @{user_info.username}\n"
            
        # Mention string
        text += f"<b>Profile:</b> <a href='tg://user?id={user_info.id}'>Link</a>\n"
        
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except TelegramError as e:
        logger.error(f"Error fetching user info for {target_id}: {e}")
        await update.effective_message.reply_text("Could not fetch information for that user.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    msg = await update.effective_message.reply_text("Pong! 🏓")
    end_time = time.time()
    
    ping_time = round((end_time - start_time) * 1000)
    await msg.edit_text(f"Pong! 🏓\nResponse time: {ping_time}ms")
