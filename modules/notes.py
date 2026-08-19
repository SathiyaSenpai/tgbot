import logging
import shlex

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

from utils.decorators import admin_required, owner_required, group_only
from utils.formatting import apply_fillings, extract_buttons

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("save", save_note), group=0)
    app.add_handler(CommandHandler("get", get_note), group=0)
    app.add_handler(CommandHandler("notes", list_notes), group=0)
    app.add_handler(CommandHandler("saved", list_notes), group=0)
    app.add_handler(CommandHandler("clear", clear_note), group=0)
    app.add_handler(CommandHandler("clearall", clearall_notes), group=0)
    app.add_handler(CommandHandler("privatenotes", toggle_privatenotes), group=0)
    
    app.add_handler(
        MessageHandler(filters.Regex(r"^#([a-zA-Z0-9_]+)"), hashtag_note), 
        group=0
    )

@group_only
@admin_required
async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args and not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Usage: /save <name> <content> or reply to media.", parse_mode=ParseMode.HTML)
        return
        
    args_str = " ".join(context.args)
    try:
        parsed_args = shlex.split(args_str)
    except ValueError:
        parsed_args = context.args
        
    if not parsed_args:
        await update.effective_message.reply_text("You need to specify a name.", parse_mode=ParseMode.HTML)
        return
        
    name = parsed_args[0].lower()
    
    reply_msg = update.effective_message.reply_to_message
    media_type = None
    media_id = None
    content = None
    
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
            content = reply_msg.text or reply_msg.caption
            
        if len(parsed_args) > 1 and not content:
            content = " ".join(parsed_args[1:])
    else:
        if len(parsed_args) < 2:
            await update.effective_message.reply_text("You need to specify content or reply to media.", parse_mode=ParseMode.HTML)
            return
        content = " ".join(parsed_args[1:])
        
    await db.execute(
        "INSERT INTO notes (chat_id, name, content, media_type, media_id, is_private, is_admin, is_protected) VALUES (?, ?, ?, ?, ?, 0, 0, 0) "
        "ON CONFLICT(chat_id, name) DO UPDATE SET content=excluded.content, media_type=excluded.media_type, media_id=excluded.media_id",
        (chat_id, name, content, media_type, media_id)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"Note <b>{name}</b> saved.", parse_mode=ParseMode.HTML)

@group_only
async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /get <name>", parse_mode=ParseMode.HTML)
        return
        
    name = context.args[0].lower()
    await send_note(update, context, name)

async def hashtag_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
        
    text = update.effective_message.text
    import re
    match = re.match(r"^#([a-zA-Z0-9_]+)", text)
    if match:
        name = match.group(1).lower()
        await send_note(update, context, name)

async def send_note(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    row = await db.fetchone("SELECT content, media_type, media_id FROM notes WHERE chat_id = ? AND name = ?", (chat_id, name))
    
    if not row:
        return
        
    is_private = await db.get_chat_setting(chat_id, "privatenotes", "0")
    
    if is_private == "1" and update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        bot_username = context.bot.username
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("View in PM", url=f"https://t.me/{bot_username}?start=note_{chat_id}_{name}")]])
        await update.effective_message.reply_text(f"Note <b>{name}</b>:", reply_markup=markup, parse_mode=ParseMode.HTML)
        return
        
    content = row["content"]
    media_type = row["media_type"]
    media_id = row["media_id"]
    
    markup = None
    if content:
        content = apply_fillings(content, update.effective_message)
        content, buttons = extract_buttons(content)
        if buttons:
            markup = InlineKeyboardMarkup(buttons)
            
    try:
        if media_type:
            if media_type == "photo":
                await update.effective_message.reply_photo(media_id, caption=content, reply_markup=markup, parse_mode=ParseMode.HTML)
            elif media_type == "video":
                await update.effective_message.reply_video(media_id, caption=content, reply_markup=markup, parse_mode=ParseMode.HTML)
            elif media_type == "document":
                await update.effective_message.reply_document(media_id, caption=content, reply_markup=markup, parse_mode=ParseMode.HTML)
            elif media_type == "sticker":
                await update.effective_message.reply_sticker(media_id, reply_markup=markup)
            elif media_type == "animation":
                await update.effective_message.reply_animation(media_id, caption=content, reply_markup=markup, parse_mode=ParseMode.HTML)
        elif content:
            await update.effective_message.reply_text(content, reply_markup=markup, parse_mode=ParseMode.HTML)
    except TelegramError as e:
        logger.error(f"Failed to send note {name}: {e}")

@group_only
async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT name FROM notes WHERE chat_id = ?", (chat_id,))
    
    if not rows:
        await update.effective_message.reply_text("No notes in this chat.", parse_mode=ParseMode.HTML)
        return
        
    text = "<b>Notes:</b>\n"
    for row in rows:
        text += f"- <code>#{row['name']}</code>\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def clear_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /clear <name>", parse_mode=ParseMode.HTML)
        return
        
    name = context.args[0].lower()
    
    row = await db.execute("DELETE FROM notes WHERE chat_id = ? AND name = ?", (chat_id, name))
    await db.commit()
    
    if row.rowcount > 0:
        await update.effective_message.reply_text(f"Note <b>{name}</b> deleted.", parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(f"Note <b>{name}</b> not found.", parse_mode=ParseMode.HTML)

@owner_required
async def clearall_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("DELETE FROM notes WHERE chat_id = ?", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Cleared all notes for this chat.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def toggle_privatenotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /privatenotes <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower()
    if val in ["on", "yes", "true"]:
        await db.set_chat_setting(chat_id, "privatenotes", "1")
    elif val in ["off", "no", "false"]:
        await db.set_chat_setting(chat_id, "privatenotes", "0")
    else:
        await update.effective_message.reply_text("Invalid value. Use on or off.", parse_mode=ParseMode.HTML)
        return
        
    await db.commit()
    await update.effective_message.reply_text(f"Private notes set to: <b>{val}</b>", parse_mode=ParseMode.HTML)
