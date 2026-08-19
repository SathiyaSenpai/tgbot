import logging
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters, ApplicationHandlerStop
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

from utils.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# Hardcoded list of commands that can be disabled
DISABLEABLE_COMMANDS = ['ban', 'kick', 'mute', 'warn', 'rules', 'notes', 'pin', 'locks']
NEVER_DISABLE = ['disable', 'enable', 'disabled', 'disabledel', 'cmds', 'start', 'help']

@group_only
@admin_required
async def disable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /disable <command>", parse_mode=ParseMode.HTML)
        return
        
    cmd = context.args[0].lower().lstrip('/')
    
    if cmd in NEVER_DISABLE:
        await update.effective_message.reply_text(f"Command <code>{cmd}</code> cannot be disabled.", parse_mode=ParseMode.HTML)
        return
        
    await db.execute(
        "INSERT OR IGNORE INTO disabled_commands (chat_id, command) VALUES (?, ?)",
        (chat_id, cmd)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"Command <code>{cmd}</code> has been disabled.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def enable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /enable <command>", parse_mode=ParseMode.HTML)
        return
        
    cmd = context.args[0].lower().lstrip('/')
    
    await db.execute(
        "DELETE FROM disabled_commands WHERE chat_id = ? AND command = ?",
        (chat_id, cmd)
    )
    await db.commit()
    
    await update.effective_message.reply_text(f"Command <code>{cmd}</code> has been enabled.", parse_mode=ParseMode.HTML)

@group_only
async def disabled_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rows = await db.fetchall("SELECT command FROM disabled_commands WHERE chat_id = ?", (chat_id,))
    
    if not rows:
        await update.effective_message.reply_text("No commands are disabled in this chat.", parse_mode=ParseMode.HTML)
        return
        
    cmds = [row[0] for row in rows]
    text = "<b>Disabled Commands:</b>\n"+ "\n".join(f"- <code>{c}</code>"for c in cmds)
    
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def disabledel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.effective_message.reply_text("Usage: /disabledel <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower() == 'on'
    await db.set_chat_setting(chat_id, 'disabledel', val)
    await db.commit()
    
    status = "enabled"if val else "disabled"
    await update.effective_message.reply_text(f"Auto-delete for disabled commands is now {status}.", parse_mode=ParseMode.HTML)

@group_only
async def cmds_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "<b>Disableable Commands:</b>\n"+ "\n".join(f"- <code>{c}</code>"for c in DISABLEABLE_COMMANDS)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def check_disabled_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return
        
    text = update.effective_message.text
    if not text.startswith('/'):
        return
        
    cmd = text.split()[0][1:].lower().split('@')[0]
    
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    is_disabled = await db.fetchval(
        "SELECT 1 FROM disabled_commands WHERE chat_id = ? AND command = ?",
        (chat_id, cmd)
    )
    
    if is_disabled:
        del_on = await db.get_chat_setting(chat_id, 'disabledel', False)
        if del_on:
            try:
                await update.effective_message.delete()
            except TelegramError:
                pass
        raise ApplicationHandlerStop()

def register(app):
    # Group -2 for middleware
    app.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.GROUPS, check_disabled_middleware), group=-2)
    
    # Group 0 for commands
    app.add_handler(CommandHandler("disable", disable_cmd), group=0)
    app.add_handler(CommandHandler("enable", enable_cmd), group=0)
    app.add_handler(CommandHandler("disabled", disabled_cmd), group=0)
    app.add_handler(CommandHandler("disabledel", disabledel_cmd), group=0)
    app.add_handler(CommandHandler("cmds", cmds_cmd), group=0)
