import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import can_pin, group_only

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("pin", pin_message), group=0)
    app.add_handler(CommandHandler("unpin", unpin_message), group=0)
    app.add_handler(CommandHandler("unpinall", unpin_all_messages), group=0)
    app.add_handler(CommandHandler("pinned", get_pinned), group=0)
    app.add_handler(CommandHandler("permapin", permapin), group=0)

@group_only
@can_pin
async def pin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    
    if not msg.reply_to_message:
        await msg.reply_text("Please reply to a message to pin it.")
        return
        
    disable_notification = True
    if context.args and context.args[0].lower() == "loud":
        disable_notification = False
        
    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=msg.reply_to_message.message_id,
            disable_notification=disable_notification
        )
        await msg.reply_text("Message pinned successfully.")
    except (TelegramError, BadRequest, Forbidden) as e:
        await msg.reply_text(f"Failed to pin message: {e}")

@group_only
@can_pin
async def unpin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    
    message_id = msg.reply_to_message.message_id if msg.reply_to_message else None
    
    try:
        await context.bot.unpin_chat_message(
            chat_id=chat.id,
            message_id=message_id
        )
        await msg.reply_text("Message unpinned successfully.")
    except (TelegramError, BadRequest, Forbidden) as e:
        await msg.reply_text(f"Failed to unpin message: {e}")

@group_only
@can_pin
async def unpin_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    
    try:
        await context.bot.unpin_all_chat_messages(chat_id=chat.id)
        await msg.reply_text("All pinned messages have been unpinned.")
    except (TelegramError, BadRequest, Forbidden) as e:
        await msg.reply_text(f"Failed to unpin messages: {e}")

@group_only
@can_pin
async def get_pinned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    
    try:
        chat_full = await context.bot.get_chat(chat.id)
        if chat_full.pinned_message:
            link = chat_full.pinned_message.link
            if link:
                await update.effective_message.reply_text(f"The current pinned message can be found <a href='{link}'>here</a>.", parse_mode=ParseMode.HTML)
            else:
                await update.effective_message.reply_text("There is a pinned message, but it doesn't have a direct link.")
        else:
            await update.effective_message.reply_text("There is no pinned message in this chat.")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Could not fetch pinned message: {e}")

@group_only
@can_pin
async def permapin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    
    if not context.args:
        await msg.reply_text("Usage: /permapin <text>")
        return
        
    text = msg.text.split(None, 1)[1]
    
    try:
        sent_msg = await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode=ParseMode.HTML
        )
        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=sent_msg.message_id,
            disable_notification=True
        )
    except (TelegramError, BadRequest, Forbidden) as e:
        await msg.reply_text(f"Failed to send and pin message: {e}")
