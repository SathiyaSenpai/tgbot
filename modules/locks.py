import logging
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

AVAILABLE_LOCKS = [
    "url", "photo", "video", "audio", "document", 
    "gif", "animation", "sticker", "voice", "contact", 
    "location", "forward", "poll", "bot", "inline"
]

def register(app):
    app.add_handler(CommandHandler("lock", lock_types), group=0)
    app.add_handler(CommandHandler("unlock", unlock_types), group=0)
    app.add_handler(CommandHandler("locks", show_locks), group=0)
    app.add_handler(CommandHandler("locktypes", show_locktypes), group=0)
    
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, enforce_locks), group=3)

@group_only
@admin_required
async def lock_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /lock <type> [type2 ...]")
        return
        
    locked = []
    invalid = []
    
    for l_type in context.args:
        l_type = l_type.lower()
        if l_type == "gif": l_type = "animation"
        if l_type in AVAILABLE_LOCKS:
            # Note: locks table setup is expected to have chat_id and lock_type
            await db.execute("INSERT OR IGNORE INTO locks (chat_id, lock_type) VALUES (?, ?)", (chat_id, l_type))
            locked.append(l_type)
        else:
            invalid.append(l_type)
            
    await db.commit()
    
    msg = ""
    if locked:
        msg += f"Locked: {', '.join(locked)}\n"
    if invalid:
        msg += f"Invalid types: {', '.join(invalid)}"
        
    await update.effective_message.reply_text(msg.strip() or "No valid types provided.")

@group_only
@admin_required
async def unlock_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /unlock <type> [type2 ...]")
        return
        
    unlocked = []
    
    for l_type in context.args:
        l_type = l_type.lower()
        if l_type == "gif": l_type = "animation"
        await db.execute("DELETE FROM locks WHERE chat_id = ? AND lock_type = ?", (chat_id, l_type))
        unlocked.append(l_type)
            
    await db.commit()
    await update.effective_message.reply_text(f"Unlocked: {', '.join(unlocked)}"if unlocked else "No valid types provided.")

@group_only
@admin_required
async def show_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT lock_type FROM locks WHERE chat_id = ?", (chat_id,))
    
    if not rows:
        await update.effective_message.reply_text("No active locks in this chat.")
        return
        
    locked_types = [row[0] for row in rows]
    await update.effective_message.reply_text(f"<b>Locked types:</b>\n- "+ "\n- ".join(locked_types), parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def show_locktypes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types_list = ", ".join(AVAILABLE_LOCKS)
    await update.effective_message.reply_text(f"Available lock types: {types_list}")

async def is_admin_or_approved(chat_id, user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return True
        return False
    except TelegramError:
        return False

async def enforce_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
        
    user = update.effective_user
    if not user or user.is_bot:
        return
        
    chat = update.effective_chat
    db = context.bot_data["db"]
    
    rows = await db.fetchall("SELECT lock_type FROM locks WHERE chat_id = ?", (chat.id,))
    if not rows:
        return
        
    locked_types = [row[0] for row in rows]
    
    if await is_admin_or_approved(chat.id, user.id, context.bot):
        return
        
    should_delete = False
    
    if "url"in locked_types:
        entities = msg.parse_entities(["url", "text_link"])
        if entities:
            should_delete = True
            
    if "photo"in locked_types and msg.photo:
        should_delete = True
    elif "video"in locked_types and msg.video:
        should_delete = True
    elif "audio"in locked_types and msg.audio:
        should_delete = True
    elif "document"in locked_types and msg.document:
        should_delete = True
    elif ("animation"in locked_types or "gif"in locked_types) and msg.animation:
        should_delete = True
    elif "sticker"in locked_types and msg.sticker:
        should_delete = True
    elif "voice"in locked_types and msg.voice:
        should_delete = True
    elif "contact"in locked_types and msg.contact:
        should_delete = True
    elif "location"in locked_types and msg.location:
        should_delete = True
    elif "forward"in locked_types and msg.forward_origin:
        should_delete = True
    elif "poll"in locked_types and msg.poll:
        should_delete = True
    elif "inline"in locked_types and msg.via_bot:
        should_delete = True
        
    if should_delete:
        try:
            await msg.delete()
        except (TelegramError, BadRequest, Forbidden):
            pass
