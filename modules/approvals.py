import logging
from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.constants import ParseMode

from utils.decorators import admin_required, owner_required, group_only
from utils.helpers import get_target_user, mention_html

logger = logging.getLogger(__name__)

@group_only
@admin_required
async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    admin = update.effective_user
    
    target_user, target_name = await get_target_user(update, context)
    if not target_user:
        await update.effective_message.reply_text("Reply to a user or provide their ID to approve them.", parse_mode=ParseMode.HTML)
        return
        
    await db.execute(
        "INSERT OR REPLACE INTO approved_users (chat_id, user_id, approved_by) VALUES (?, ?, ?)",
        (chat_id, target_user, admin.id)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"User {mention_html(target_user, target_name)} is now approved.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def unapprove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    target_user, target_name = await get_target_user(update, context)
    if not target_user:
        await update.effective_message.reply_text("Reply to a user or provide their ID to unapprove them.", parse_mode=ParseMode.HTML)
        return
        
    await db.execute(
        "DELETE FROM approved_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, target_user)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"User {mention_html(target_user, target_name)} is no longer approved.", parse_mode=ParseMode.HTML)

@group_only
async def approved_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT user_id FROM approved_users WHERE chat_id = ?", (chat_id,))
    if not rows:
        await update.effective_message.reply_text("No users are approved in this chat.", parse_mode=ParseMode.HTML)
        return
        
    text = "<b>Approved Users:</b>\n"
    for row in rows:
        uid = row[0]
        text += f"- <code>{uid}</code>\n"
        
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
async def approval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    target_user, target_name = await get_target_user(update, context)
    if not target_user:
        target_user = update.effective_user.id
        target_name = update.effective_user.first_name
        
    is_approved = await db.fetchval(
        "SELECT 1 FROM approved_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, target_user)
    )
    
    status = "is approved" if is_approved else "is not approved"
    await update.effective_message.reply_text(f"User {mention_html(target_user, target_name)} {status}.", parse_mode=ParseMode.HTML)

@group_only
@owner_required
async def unapproveall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("DELETE FROM approved_users WHERE chat_id = ?", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("All approved users have been cleared.", parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("approve", approve_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "approve", approve_cmd), group=0)
    app.add_handler(CommandHandler("unapprove", unapprove_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "unapprove", unapprove_cmd), group=0)
    app.add_handler(CommandHandler("approved", approved_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "approved", approved_cmd), group=0)
    app.add_handler(CommandHandler("approval", approval_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "approval", approval_cmd), group=0)
    app.add_handler(CommandHandler("unapproveall", unapproveall_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "unapproveall", unapproveall_cmd), group=0)
