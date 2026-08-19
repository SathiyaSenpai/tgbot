import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.constants import ParseMode, ChatType

from utils.decorators import is_user_admin

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("connect", connect_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "connect", connect_cmd), group=0)
    app.add_handler(CommandHandler("disconnect", disconnect_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "disconnect", disconnect_cmd), group=0)
    app.add_handler(CommandHandler("connection", connection_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "connection", connection_cmd), group=0)
    
async def connect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    bot_username = context.bot.username
    db = context.bot_data["db"]
    
    # If in a group, send a deep link button
    if chat_type in (ChatType.GROUP, ChatType.SUPERGROUP):
        chat_id = update.effective_chat.id
        if not await is_user_admin(chat_id, user_id, context, update):
            await update.effective_message.reply_text("You must be an admin to connect to this group.")
            return
            
        url = f"https://t.me/{bot_username}?start=connect_{chat_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Connect in PM", url=url)]])
        await update.effective_message.reply_text("Tap below to connect to this group in my DMs:", reply_markup=keyboard)
        return
        
    # If in PM, allow /connect <chat_id>
    if chat_type == ChatType.PRIVATE:
        if not context.args:
            await update.effective_message.reply_text(
                "Usage: <code>/connect &lt;chat_id&gt;</code>\n"
                "Or, just send <code>/connect</code> in the group you want to manage to get a button.",
                parse_mode=ParseMode.HTML
            )
            return
            
        try:
            chat_id = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("Invalid Chat ID.")
            return
            
        if not await is_user_admin(chat_id, user_id, context, update):
            await update.effective_message.reply_text("You must be an admin in that group to connect to it.")
            return
            
        await db.execute(
            "INSERT INTO connections (user_id, chat_id) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET chat_id = ?",
            (user_id, chat_id, chat_id),
        )
        await db.commit()
        
        try:
            chat = await context.bot.get_chat(chat_id)
            chat_title = chat.title
        except:
            chat_title = str(chat_id)
            
        await update.effective_message.reply_text(f"✅ Successfully connected to <b>{chat_title}</b>.", parse_mode=ParseMode.HTML)
        
async def disconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("Use this command in PM.")
        return
        
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    
    await db.execute("DELETE FROM connections WHERE user_id = ?", (user_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Disconnected from all groups.")
    
async def connection_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("Use this command in PM.")
        return
        
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    
    row = await db.fetchone("SELECT chat_id FROM connections WHERE user_id = ?", (user_id,))
    if not row:
        await update.effective_message.reply_text("You are not connected to any group.")
        return
        
    chat_id = row[0]
    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title
    except:
        chat_title = str(chat_id)
        
    await update.effective_message.reply_text(f"You are currently connected to <b>{chat_title}</b> (<code>{chat_id}</code>).", parse_mode=ParseMode.HTML)
