import logging
from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from telegram.error import TelegramError

from utils.decorators import admin_required, group_only
from utils.helpers import mention_html

logger = logging.getLogger(__name__)

async def notify_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, reporter, reported, message_text):
    chat = update.effective_chat
    
    report_text = (
        f"🚨 <b>Report in {chat.title}</b>\n\n"
        f"<b>Reporter:</b> {mention_html(reporter.id, reporter.first_name)}\n"
        f"<b>Reported User:</b> {mention_html(reported.id, reported.first_name)}\n"
        f"<b>Message:</b> {message_text}\n"
    )
    
    # Optional log channel notification could go here if integrated.
    
    try:
        admins = await chat.get_administrators()
        for admin in admins:
            if not admin.user.is_bot:
                try:
                    await context.bot.send_message(
                        admin.user.id,
                        report_text,
                        parse_mode=ParseMode.HTML
                    )
                except TelegramError:
                    pass
    except TelegramError:
        pass


@group_only
async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    reports_enabled = await db.get_chat_setting(chat_id, 'reports_enabled', True)
    if not reports_enabled:
        return
        
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text("You must reply to a message to report it.", parse_mode=ParseMode.HTML)
        return
        
    reporter = update.effective_user
    reported = msg.reply_to_message.from_user
    
    if reported.id == reporter.id:
        await msg.reply_text("You cannot report yourself.", parse_mode=ParseMode.HTML)
        return
        
    if reported.is_bot:
        await msg.reply_text("You cannot report bots.", parse_mode=ParseMode.HTML)
        return
        
    await notify_admins(update, context, reporter, reported, msg.reply_to_message.text or "<i>No text</i>")
    await msg.reply_text("Report sent to administrators.", parse_mode=ParseMode.HTML)

@group_only
async def admin_mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    reports_enabled = await db.get_chat_setting(chat_id, 'reports_enabled', True)
    if not reports_enabled:
        return
        
    msg = update.effective_message
    if not msg.reply_to_message:
        return # Need reply to report
        
    reporter = update.effective_user
    reported = msg.reply_to_message.from_user
    
    if reported.id == reporter.id or reported.is_bot:
        return
        
    await notify_admins(update, context, reporter, reported, msg.reply_to_message.text or "<i>No text</i>")
    await msg.reply_text("Report sent to administrators.", parse_mode=ParseMode.HTML)


@group_only
@admin_required
async def reports_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.effective_message.reply_text("Usage: /reports <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower() == 'on'
    await db.set_chat_setting(chat_id, 'reports_enabled', val)
    await db.commit()
    
    status = "enabled" if val else "disabled"
    await update.effective_message.reply_text(f"Reports are now {status}.", parse_mode=ParseMode.HTML)

def register(app):
    app.add_handler(CommandHandler("report", report_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "report", report_cmd), group=0)
    app.add_handler(CommandHandler("reports", reports_toggle), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "reports", reports_toggle), group=0)
    app.add_handler(MessageHandler(filters.Regex(r'(?i)@admin') & filters.ChatType.GROUPS, admin_mention_handler), group=0)
