import logging
import shlex

from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.error import TelegramError

from utils.decorators import admin_required, owner_required, group_only
from utils.formatting import apply_fillings, extract_buttons

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("filter", set_filter), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "filter", set_filter), group=0)
    app.add_handler(CommandHandler("filters", list_filters), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "filters", list_filters), group=0)
    app.add_handler(CommandHandler("stop", stop_filter), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "stop", stop_filter), group=0)
    app.add_handler(CommandHandler("stopall", stopall_filters), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "stopall", stopall_filters), group=0)
    
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, filter_scanner), 
        group=2
    )

@group_only
@admin_required
async def set_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args and not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Usage: /filter <trigger> <response> or reply to media.", parse_mode=ParseMode.HTML)
        return
        
    args_str = " ".join(context.args)
    try:
        parsed_args = shlex.split(args_str)
    except ValueError:
        parsed_args = context.args
        
    if not parsed_args:
        await update.effective_message.reply_text("You need to specify a trigger.", parse_mode=ParseMode.HTML)
        return
        
    trigger_raw = parsed_args[0]
    match_mode = "contains"
    trigger_text = trigger_raw.lower()
    
    if trigger_raw.lower().startswith("exact:"):
        match_mode = "exact"
        trigger_text = trigger_raw[6:].lower()
    elif trigger_raw.lower().startswith("prefix:"):
        match_mode = "prefix"
        trigger_text = trigger_raw[7:].lower()
        
    reply_msg = update.effective_message.reply_to_message
    media_type = None
    media_id = None
    response = None
    
    if reply_msg:
        if reply_msg.photo:
            media_type = "photo"
            media_id = reply_msg.photo[-1].file_id
        elif reply_msg.video:
            media_type = "video"
            media_id = reply_msg.video.file_id
        elif reply_msg.document:
            media_type = "document"
            media_id = reply_msg.document.file_id
        elif reply_msg.sticker:
            media_type = "sticker"
            media_id = reply_msg.sticker.file_id
        elif reply_msg.animation:
            media_type = "animation"
            media_id = reply_msg.animation.file_id
            
        if reply_msg.text or reply_msg.caption:
            response = reply_msg.text or reply_msg.caption
            
        if len(parsed_args) > 1 and not response:
            response = " ".join(parsed_args[1:])
    else:
        if len(parsed_args) < 2:
            await update.effective_message.reply_text("You need to specify a response or reply to media.", parse_mode=ParseMode.HTML)
            return
        response = " ".join(parsed_args[1:])
        
    await db.execute(
        "INSERT INTO filters (chat_id, trigger_text, match_mode, response, media_type, media_id) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(chat_id, trigger_text) DO UPDATE SET match_mode=excluded.match_mode, response=excluded.response, media_type=excluded.media_type, media_id=excluded.media_id",
        (chat_id, trigger_text, match_mode, response, media_type, media_id)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"Filter added for <b>{trigger_text}</b>.", parse_mode=ParseMode.HTML)

@group_only
async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT trigger_text, match_mode FROM filters WHERE chat_id = ?", (chat_id,))
    
    if not rows:
        await update.effective_message.reply_text("No filters in this chat.", parse_mode=ParseMode.HTML)
        return
        
    text = "<b>Filters:</b>\n"
    for row in rows:
        trigger = row["trigger_text"]
        mode = row["match_mode"]
        text += f"- <code>{trigger}</code> ({mode})\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def stop_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /stop <trigger>", parse_mode=ParseMode.HTML)
        return
        
    args_str = " ".join(context.args)
    try:
        parsed_args = shlex.split(args_str)
        trigger = parsed_args[0].lower()
    except ValueError:
        trigger = context.args[0].lower()
        
    row = await db.execute("DELETE FROM filters WHERE chat_id = ? AND trigger_text = ?", (chat_id, trigger))
    await db.commit()
    
    if row.rowcount > 0:
        await update.effective_message.reply_text(f"Filter <b>{trigger}</b> removed.", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"Filter <b>{trigger}</b> not found.", parse_mode=ParseMode.HTML)

@owner_required
async def stopall_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("DELETE FROM filters WHERE chat_id = ?", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Cleared all filters for this chat.", parse_mode=ParseMode.HTML)

async def filter_scanner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
        
    chat = update.effective_chat
    update.effective_user
    db = context.bot_data["db"]
    text = update.effective_message.text.lower()
    
    filters_rows = await db.fetchall("SELECT trigger_text, match_mode, response, media_type, media_id FROM filters WHERE chat_id = ?", (chat.id,))
    
    for row in filters_rows:
        trigger = row["trigger_text"]
        mode = row["match_mode"]
        
        match = False
        if mode == "exact" and text == trigger:
            match = True
        elif mode == "prefix" and text.startswith(trigger):
            match = True
        elif mode == "contains" and trigger in text:
            match = True
            
        if match:
            response_text = row["response"]
            media_type = row["media_type"]
            media_id = row["media_id"]
            
            markup = None
            if response_text:
                response_text = apply_fillings(response_text, update.effective_message)
                response_text, buttons = extract_buttons(response_text)
                if buttons:
                    from telegram import InlineKeyboardMarkup
                    markup = InlineKeyboardMarkup(buttons)
            
            try:
                if media_type:
                    if media_type == "photo":
                        await update.effective_message.reply_photo(media_id, caption=response_text, reply_markup=markup, parse_mode=ParseMode.HTML)
                    elif media_type == "video":
                        await update.effective_message.reply_video(media_id, caption=response_text, reply_markup=markup, parse_mode=ParseMode.HTML)
                    elif media_type == "document":
                        await update.effective_message.reply_document(media_id, caption=response_text, reply_markup=markup, parse_mode=ParseMode.HTML)
                    elif media_type == "sticker":
                        await update.effective_message.reply_sticker(media_id, reply_markup=markup)
                    elif media_type == "animation":
                        await update.effective_message.reply_animation(media_id, caption=response_text, reply_markup=markup, parse_mode=ParseMode.HTML)
                elif response_text:
                    await update.effective_message.reply_text(response_text, reply_markup=markup, parse_mode=ParseMode.HTML)
            except TelegramError as e:
                logger.error(f"Failed to send filter response: {e}")
            break
