import logging
from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import can_delete, group_only

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("purge", purge), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "purge", purge), group=0)
    app.add_handler(CommandHandler("spurge", spurge), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "spurge", spurge), group=0)
    app.add_handler(CommandHandler("del", del_message), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "del", del_message), group=0)

@group_only
@can_delete
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_purge(update, context, silent=False)

@group_only
@can_delete
async def spurge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_purge(update, context, silent=True)

async def do_purge(update: Update, context: ContextTypes.DEFAULT_TYPE, silent: bool = False):
    msg = update.effective_message
    chat = update.effective_chat
    
    if not msg.reply_to_message:
        if not silent:
            await msg.reply_text("Reply to a message to start purging.")
        return
        
    start_id = msg.reply_to_message.message_id
    end_id = msg.message_id
    
    if context.args and context.args[0].isdigit():
        count = int(context.args[0])
        end_id = start_id + count
        if not silent:
            # Also delete the command if doing a limited forward purge
            message_ids_to_delete = list(range(start_id, end_id + 1)) + [msg.message_id]
        else:
            message_ids_to_delete = list(range(start_id, end_id + 1)) + [msg.message_id]
    else:
        message_ids_to_delete = list(range(start_id, end_id + 1))

    deleted_count = 0
    
    for i in range(0, len(message_ids_to_delete), 100):
        batch = message_ids_to_delete[i:i+100]
        try:
            await context.bot.delete_messages(chat_id=chat.id, message_ids=batch)
            deleted_count += len(batch)
        except (TelegramError, BadRequest, Forbidden) as e:
            logger.warning(f"Failed to delete batch: {e}")
            
    if not silent:
        try:
            await msg.reply_text(f"Purge complete. Deleted roughly {deleted_count} messages.")
            # Optional: wait and delete the confirmation
        except Exception:
            pass
            
@group_only
@can_delete
async def del_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a message to delete it.")
        return
        
    try:
        await context.bot.delete_messages(
            chat_id=chat.id,
            message_ids=[msg.reply_to_message.message_id, msg.message_id]
        )
    except (TelegramError, BadRequest, Forbidden) as e:
        await msg.reply_text(f"Failed to delete message: {e}")
