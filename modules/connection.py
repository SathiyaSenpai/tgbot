import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import private_only

logger = logging.getLogger(__name__)

async def connect_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user = update.effective_user
    args = context.args

    if not args:
        await update.effective_message.reply_text("Usage: /connect <chat_id>", parse_mode=ParseMode.HTML)
        return

    chat_id_str = args[0]
    
    # Simple validation
    try:
        chat_id = int(chat_id_str)
    except ValueError:
        await update.effective_message.reply_text("Invalid chat ID format.", parse_mode=ParseMode.HTML)
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status not in ['administrator', 'creator']:
            await update.effective_message.reply_text("You must be an admin of that chat to connect to it.", parse_mode=ParseMode.HTML)
            return
            
        chat = await context.bot.get_chat(chat_id)
    except (BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Could not connect: {str(e)}", parse_mode=ParseMode.HTML)
        return
    except TelegramError as e:
        logger.error(f"Error checking chat member: {e}")
        await update.effective_message.reply_text("An error occurred.", parse_mode=ParseMode.HTML)
        return

    await db.execute(
        "INSERT INTO connections (user_id, chat_id) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id",
        (user.id, chat_id)
    )
    await db.commit()

    await update.effective_message.reply_text(f"Successfully connected to <b>{chat.title}</b>.", parse_mode=ParseMode.HTML)


async def connect_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    bot = await context.bot.get_me()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Connect in PM", url=f"t.me/{bot.username}?start=connect_{chat.id}")]
    ])
    
    await update.effective_message.reply_text(
        "Click the button below to connect to this chat in PM.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

async def connect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        text = update.effective_message.text
        if text.startswith("/start connect_"):
            context.args = [text.split("_", 1)[1]]
        await connect_pm(update, context)
    else:
        # Only admins can trigger the button
        await connect_group(update, context)

@private_only
async def disconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user = update.effective_user

    await db.execute("DELETE FROM connections WHERE user_id = ?", (user.id,))
    await db.commit()

    await update.effective_message.reply_text("Disconnected.", parse_mode=ParseMode.HTML)

@private_only
async def connection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user = update.effective_user

    chat_id = await db.fetchval("SELECT chat_id FROM connections WHERE user_id = ?", (user.id,))
    
    if not chat_id:
        await update.effective_message.reply_text("You are not connected to any chat.", parse_mode=ParseMode.HTML)
        return
        
    try:
        chat = await context.bot.get_chat(chat_id)
        title = chat.title
    except Exception:
        title = "Unknown Chat"

    await update.effective_message.reply_text(f"You are currently connected to <b>{title}</b> (<code>{chat_id}</code>).", parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("connect", connect_handler), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "connect", connect_handler), group=0)
    app.add_handler(CommandHandler("start", connect_handler, filters=filters.Regex(r'^/start connect_')), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "start", connect_handler, filters=filters.Regex(r'^/start connect_')), group=0)
    app.add_handler(CommandHandler("disconnect", disconnect_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "disconnect", disconnect_cmd), group=0)
    app.add_handler(CommandHandler("connection", connection_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "connection", connection_cmd), group=0)
