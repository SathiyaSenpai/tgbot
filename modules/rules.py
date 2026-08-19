import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.constants import ParseMode

from utils.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("rules", show_rules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "rules", show_rules), group=0)
    app.add_handler(CommandHandler("setrules", set_rules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setrules", set_rules), group=0)
    app.add_handler(CommandHandler("clearrules", clear_rules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "clearrules", clear_rules), group=0)
    app.add_handler(CommandHandler("privaterules", toggle_privaterules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "privaterules", toggle_privaterules), group=0)
    app.add_handler(CommandHandler("setrulesbutton", set_rules_button), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setrulesbutton", set_rules_button), group=0)
    app.add_handler(CommandHandler("resetrulesbutton", reset_rules_button), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "resetrulesbutton", reset_rules_button), group=0)

@group_only
async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    rules_text = await db.get_chat_setting(chat_id, "rules_text", None)
    if not rules_text:
        await update.effective_message.reply_text("No rules set for this chat.", parse_mode=ParseMode.HTML)
        return
        
    privaterules = await db.get_chat_setting(chat_id, "rules_private", 1)
    
    if str(privaterules).lower() in ("1", "true"):
        button_text = await db.get_chat_setting(chat_id, "rules_button_text", "📜 Read Rules")
        bot_username = context.bot.username
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=f"https://t.me/{bot_username}?start=rules_{chat_id}")]])
        await update.effective_message.reply_text("Click the button below to read the rules.", reply_markup=markup)
    else:
        await update.effective_message.reply_text(rules_text, parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setrules <text>", parse_mode=ParseMode.HTML)
        return
        
    msg_text = update.effective_message.text
    command_len = len(update.effective_message.text.split()[0])
    rules_text = msg_text[command_len:].strip()
    
    await db.set_chat_setting(chat_id, "rules_text", rules_text)
    await db.commit()
    
    await update.effective_message.reply_text("Rules set for this chat.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def clear_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("UPDATE chat_settings SET setting_value = NULL WHERE chat_id = ? AND setting_name = 'rules_text'", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Rules cleared for this chat.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def toggle_privaterules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /privaterules <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower()
    if val in ["on", "yes", "true"]:
        await db.set_chat_setting(chat_id, "rules_private", "1")
    elif val in ["off", "no", "false"]:
        await db.set_chat_setting(chat_id, "rules_private", "0")
    else:
        await update.effective_message.reply_text("Invalid value. Use on or off.", parse_mode=ParseMode.HTML)
        return
        
    await db.commit()
    await update.effective_message.reply_text(f"Private rules set to: <b>{val}</b>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def set_rules_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setrulesbutton <text>", parse_mode=ParseMode.HTML)
        return
        
    button_text = " ".join(context.args)
    
    await db.set_chat_setting(chat_id, "rules_button_text", button_text)
    await db.commit()
    
    await update.effective_message.reply_text(f"Rules button text set to: <b>{button_text}</b>", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def reset_rules_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    await db.execute("UPDATE chat_settings SET setting_value = NULL WHERE chat_id = ? AND setting_name = 'rules_button_text'", (chat_id,))
    await db.commit()
    
    await update.effective_message.reply_text("Rules button text reset to default.", parse_mode=ParseMode.HTML)
