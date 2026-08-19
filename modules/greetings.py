import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ChatMemberHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import admin_required, group_only
from utils.formatting import format_welcome

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("welcome", welcome), group=0)
    app.add_handler(CommandHandler("setwelcome", setwelcome), group=0)
    app.add_handler(CommandHandler("resetwelcome", resetwelcome), group=0)
    app.add_handler(CommandHandler("goodbye", goodbye), group=0)
    app.add_handler(CommandHandler("setgoodbye", setgoodbye), group=0)
    app.add_handler(CommandHandler("resetgoodbye", resetgoodbye), group=0)
    app.add_handler(CommandHandler("cleanwelcome", cleanwelcome), group=0)
    app.add_handler(CommandHandler("cleanservice", cleanservice), group=0)
    
    app.add_handler(ChatMemberHandler(chat_member_event, ChatMemberHandler.CHAT_MEMBER), group=4)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, delete_service_message), group=4)

@group_only
@admin_required
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /welcome <on|off>", parse_mode=ParseMode.HTML)
        return
        
    arg = context.args[0].lower()
    if arg in ("on", "true", "1"):
        await db.set_chat_setting(chat_id, "welcome_enabled", 1)
        await db.commit()
        await update.effective_message.reply_text("Welcome messages enabled.", parse_mode=ParseMode.HTML)
    elif arg in ("off", "false", "0"):
        await db.set_chat_setting(chat_id, "welcome_enabled", 0)
        await db.commit()
        await update.effective_message.reply_text("Welcome messages disabled.", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("Usage: /welcome <on|off>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setwelcome <text>", parse_mode=ParseMode.HTML)
        return
        
    text = update.effective_message.text.split(None, 1)[1]
    await db.set_chat_setting(chat_id, "welcome_text", text)
    await db.commit()
    await update.effective_message.reply_text("Welcome message updated.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def resetwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    default_text = "Welcome {mention} to {chatname}! "
    
    await db.set_chat_setting(chat_id, "welcome_text", default_text)
    await db.commit()
    await update.effective_message.reply_text("Welcome message reset to default.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /goodbye <on|off>", parse_mode=ParseMode.HTML)
        return
        
    arg = context.args[0].lower()
    if arg in ("on", "true", "1"):
        await db.set_chat_setting(chat_id, "goodbye_enabled", 1)
        await db.commit()
        await update.effective_message.reply_text("Goodbye messages enabled.", parse_mode=ParseMode.HTML)
    elif arg in ("off", "false", "0"):
        await db.set_chat_setting(chat_id, "goodbye_enabled", 0)
        await db.commit()
        await update.effective_message.reply_text("Goodbye messages disabled.", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("Usage: /goodbye <on|off>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setgoodbye <text>", parse_mode=ParseMode.HTML)
        return
        
    text = update.effective_message.text.split(None, 1)[1]
    await db.set_chat_setting(chat_id, "goodbye_text", text)
    await db.commit()
    await update.effective_message.reply_text("Goodbye message updated.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def resetgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    default_text = "{first} left the chat."
    
    await db.set_chat_setting(chat_id, "goodbye_text", default_text)
    await db.commit()
    await update.effective_message.reply_text("Goodbye message reset to default.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def cleanwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /cleanwelcome <on|off>", parse_mode=ParseMode.HTML)
        return
        
    arg = context.args[0].lower()
    if arg in ("on", "true", "1"):
        await db.set_chat_setting(chat_id, "clean_welcome", 1)
        await db.commit()
        await update.effective_message.reply_text("Will now delete previous welcome messages.", parse_mode=ParseMode.HTML)
    elif arg in ("off", "false", "0"):
        await db.set_chat_setting(chat_id, "clean_welcome", 0)
        await db.commit()
        await update.effective_message.reply_text("Will no longer delete previous welcome messages.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def cleanservice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /cleanservice <on|off>", parse_mode=ParseMode.HTML)
        return
        
    arg = context.args[0].lower()
    if arg in ("on", "true", "1"):
        await db.set_chat_setting(chat_id, "clean_service", 1)
        await db.commit()
        await update.effective_message.reply_text("Will now delete join/leave service messages.", parse_mode=ParseMode.HTML)
    elif arg in ("off", "false", "0"):
        await db.set_chat_setting(chat_id, "clean_service", 0)
        await db.commit()
        await update.effective_message.reply_text("Will no longer delete join/leave service messages.", parse_mode=ParseMode.HTML)

async def chat_member_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    
    result = update.chat_member
    if not result:
        return
        
    chat = result.chat
    user = result.new_chat_member.user
    
    if user.is_bot:
        return
        
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    
    # User joined
    if old_status in ["left", "kicked"] and new_status in ["member", "restricted"]:
        welcome_enabled = await db.get_chat_setting(chat.id, "welcome_enabled", 0)
        clean_welcome = await db.get_chat_setting(chat.id, "clean_welcome", 0)
        
        if welcome_enabled:
            welcome_text = await db.get_chat_setting(chat.id, "welcome_text", "Welcome {mention} to {chatname}! ")
            
            try:
                formatted_text, markup = format_welcome(welcome_text, user, chat)
                msg = await context.bot.send_message(
                    chat.id, 
                    formatted_text, 
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                )
                
                if clean_welcome:
                    last_id = await db.get_chat_setting(chat.id, "last_welcome_msg_id", 0)
                    if last_id:
                        try:
                            await context.bot.delete_message(chat.id, last_id)
                        except (TelegramError, BadRequest):
                            pass
                    
                    await db.set_chat_setting(chat.id, "last_welcome_msg_id", msg.message_id)
                    await db.commit()
            except Exception as e:
                logger.error(f"Error sending welcome: {e}")
                
    # User left
    elif old_status in ["member", "restricted", "administrator"] and new_status in ["left", "kicked"]:
        goodbye_enabled = await db.get_chat_setting(chat.id, "goodbye_enabled", 0)
        
        if goodbye_enabled:
            goodbye_text = await db.get_chat_setting(chat.id, "goodbye_text", "{first} left the chat.")
            try:
                formatted_text, markup = format_welcome(goodbye_text, user, chat)
                await context.bot.send_message(
                    chat.id,
                    formatted_text,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Error sending goodbye: {e}")

async def delete_service_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    if not update.effective_chat or not update.effective_message:
        return
    
    clean_service = await db.get_chat_setting(update.effective_chat.id, "clean_service", 0)
    if clean_service:
        try:
            await update.effective_message.delete()
        except (TelegramError, BadRequest):
            pass
