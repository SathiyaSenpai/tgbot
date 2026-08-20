"""
Senpai's Bot - Welcome Module
Generates a unique, AI-powered Kuudere welcome message when a new member joins.
"""
import logging
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, PrefixHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatType

from modules.ai_engine import generate_reply
from utils.decorators import admin_required, group_only
from utils.helpers import user_mention

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("welcome", toggle_welcome), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "welcome", toggle_welcome), group=0)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members), group=0)

@group_only
@admin_required
async def toggle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    if not db:
        return
        
    chat_id = update.effective_chat.id
    args = context.args
    
    if not args or args[0].lower() not in ["on", "off"]:
        await update.effective_message.reply_text("Usage: /welcome <on|off>")
        return
        
    val = 1 if args[0].lower() == "on" else 0
    await db.set_chat_setting(chat_id, "welcome_enabled", val)
    await db.commit()
    
    status = "enabled" if val else "disabled"
    await update.effective_message.reply_text(f"✅ AI welcome messages {status}.")

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
        
    db = context.bot_data.get("db")
    chat_id = update.effective_chat.id
    
    if db:
        is_enabled = await db.get_chat_setting(chat_id, "welcome_enabled", 1)
        if not is_enabled:
            return

    bot_id = context.bot.id
    for new_member in msg.new_chat_members:
        if new_member.id == bot_id:
            # The bot itself was added
            await msg.reply_text("Oh, I was added here. Fine. I'm Scarlet. Don't spam me.")
            continue
            
        # It's a user. Generate an AI welcome.
        user_name = new_member.first_name
        prompt = (
            f"[System Instruction: A new user named {user_name} just joined the group. "
            "Welcome them briefly. 1 sentence max. No GIFs. Stay in your Kuudere persona.]"
        )
        
        try:
            reply_text, send_gif, gif_query = await generate_reply(
                chat_id=chat_id,
                user_name="System",
                user_text=prompt,
                db=db,
            )
            
            mention = user_mention(new_member)
            safe_reply = (reply_text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            final_text = f"{mention} {safe_reply}"
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=final_text,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"[Welcome] Error generating welcome for {user_name}: {e}")
