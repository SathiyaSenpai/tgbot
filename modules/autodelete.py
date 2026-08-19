import logging
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError

from utils.decorators import admin_required

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("cleanmsg", cleanmsg), group=0)
    app.add_handler(CommandHandler("keepmsg", keepmsg), group=0)
    app.add_handler(CommandHandler("cleancommand", cleancommand), group=0)
    app.add_handler(CommandHandler("keepcommand", keepcommand), group=0)

async def auto_delete_message(message, delay=300):
    async def delete_task():
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except TelegramError as e:
            logger.debug(f"Failed to auto-delete message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in auto_delete_message: {e}")
            
    asyncio.create_task(delete_task())

async def delete_command_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_message:
        return
        
    db = context.bot_data.get("db")
    if not db:
        return
        
    try:
        clean_cmds = await db.get_chat_setting(update.effective_chat.id, "clean_commands", "off")
        if clean_cmds == "on":
            await update.effective_message.delete()
    except TelegramError:
        pass # Ignore deletion errors
    except Exception as e:
        logger.error(f"Error deleting command message: {e}")

@admin_required
async def cleanmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        if context.args and context.args[0].lower() in ["on", "off"]:
            val = context.args[0].lower()
        else:
            val = "on"
            
        await db.set_chat_setting(chat_id, "clean_messages", val)
        await db.commit()
        
        msg = await update.effective_message.reply_text(f"Bot message auto-deletion set to: <b>{val.upper()}</b>", parse_mode="HTML")
        if val == "on":
            await auto_delete_message(msg, 300)
    except Exception as e:
        logger.error(f"Error setting cleanmsg: {e}")

@admin_required
async def keepmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        await db.set_chat_setting(chat_id, "clean_messages", "off")
        await db.commit()
        await update.effective_message.reply_text("Bot message auto-deletion disabled.")
    except Exception as e:
        logger.error(f"Error disabling cleanmsg: {e}")

@admin_required
async def cleancommand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        if context.args and context.args[0].lower() in ["on", "off"]:
            val = context.args[0].lower()
        else:
            val = "on"
            
        await db.set_chat_setting(chat_id, "clean_commands", val)
        await db.commit()
        
        msg = await update.effective_message.reply_text(f"Command message auto-deletion set to: <b>{val.upper()}</b>", parse_mode="HTML")
        
        clean_msgs = await db.get_chat_setting(chat_id, "clean_messages", "off")
        if clean_msgs == "on":
            await auto_delete_message(msg, 300)
    except Exception as e:
        logger.error(f"Error setting cleancommand: {e}")

@admin_required
async def keepcommand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        await db.set_chat_setting(chat_id, "clean_commands", "off")
        await db.commit()
        await update.effective_message.reply_text("Command message auto-deletion disabled.")
    except Exception as e:
        logger.error(f"Error disabling cleancommand: {e}")
