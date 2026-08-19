import logging
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from telegram.ext import CommandHandler, ChatMemberHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError

from utils.decorators import admin_required, group_only
from utils.helpers import parse_time, mention_html

logger = logging.getLogger(__name__)

@group_only
@admin_required
async def captcha_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.effective_message.reply_text("Usage: /captcha <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower() == 'on'
    await db.set_chat_setting(chat_id, 'captcha_enabled', val)
    await db.commit()
    
    status = "enabled" if val else "disabled"
    await update.effective_message.reply_text(f"CAPTCHA is now {status}.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def captchamode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args or context.args[0].lower() not in ['math', 'button']:
        await update.effective_message.reply_text("Usage: /captchamode <math|button>", parse_mode=ParseMode.HTML)
        return
        
    mode = context.args[0].lower()
    await db.set_chat_setting(chat_id, 'captcha_mode', mode)
    await db.commit()
    
    await update.effective_message.reply_text(f"CAPTCHA mode set to {mode}.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def captchatime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /captchatime <time> (e.g. 5m)", parse_mode=ParseMode.HTML)
        return
        
    time_str = context.args[0]
    seconds = parse_time(time_str)
    if not seconds:
        await update.effective_message.reply_text("Invalid time format.", parse_mode=ParseMode.HTML)
        return
        
    await db.set_chat_setting(chat_id, 'captcha_timeout', seconds)
    await db.commit()
    
    await update.effective_message.reply_text(f"CAPTCHA timeout set to {time_str}.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def captchakick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.effective_message.reply_text("Usage: /captchakick <on|off>", parse_mode=ParseMode.HTML)
        return
        
    val = context.args[0].lower() == 'on'
    await db.set_chat_setting(chat_id, 'captcha_kick', val)
    await db.commit()
    
    status = "kick" if val else "mute"
    await update.effective_message.reply_text(f"Action on CAPTCHA timeout is now {status}.", parse_mode=ParseMode.HTML)

@group_only
@admin_required
async def setcaptchatext_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /setcaptchatext <text>", parse_mode=ParseMode.HTML)
        return
        
    text = update.effective_message.text.split(None, 1)[1]
    await db.set_chat_setting(chat_id, 'captcha_text', text)
    await db.commit()
    
    await update.effective_message.reply_text("CAPTCHA text updated.", parse_mode=ParseMode.HTML)

async def captcha_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    chat_id = data['chat_id']
    user_id = data['user_id']
    msg_id = data['msg_id']
    
    db = context.bot_data["db"]
    
    is_pending = await db.fetchval(
        "SELECT 1 FROM captcha_pending WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    )
    
    if not is_pending:
        return
        
    kick = await db.get_chat_setting(chat_id, 'captcha_kick', False)
    
    try:
        if kick:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id) # Kick
        
        await context.bot.delete_message(chat_id, msg_id)
    except TelegramError:
        pass
        
    await db.execute("DELETE FROM captcha_pending WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    await db.commit()

async def new_member_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = context.bot_data["db"]
    
    result = update.chat_member
    if result.new_chat_member.status != ChatMemberStatus.MEMBER:
        return
    if result.old_chat_member.status != ChatMemberStatus.LEFT and result.old_chat_member.status != ChatMemberStatus.KICKED:
        return
        
    user = result.new_chat_member.user
    if user.is_bot:
        return
        
    enabled = await db.get_chat_setting(chat.id, 'captcha_enabled', False)
    if not enabled:
        return
        
    is_approved = await db.fetchval("SELECT 1 FROM approved_users WHERE chat_id = ? AND user_id = ?", (chat.id, user.id))
    if is_approved:
        return

    # Mute
    try:
        await context.bot.restrict_chat_member(
            chat.id, user.id,
            ChatPermissions(can_send_messages=False)
        )
    except TelegramError:
        return # Cannot mute, give up
        
    mode = await db.get_chat_setting(chat.id, 'captcha_mode', 'math')
    timeout = await db.get_chat_setting(chat.id, 'captcha_timeout', 300) # 5m default
    text = await db.get_chat_setting(chat.id, 'captcha_text', "Please solve this CAPTCHA to speak:")
    
    keyboard = []
    answer = "pass"
    
    if mode == 'math':
        n1 = random.randint(1, 10)
        n2 = random.randint(1, 10)
        correct = n1 + n2
        answer = str(correct)
        
        options = [correct, correct + random.randint(1,5), correct - random.randint(1,3), correct + random.randint(6,10)]
        random.shuffle(options)
        
        text = f"{text}\n\nWhat is {n1} + {n2}?"
        
        row = []
        for opt in options:
            cb_data = f"captcha_{chat.id}_{user.id}_{opt}"
            row.append(InlineKeyboardButton(str(opt), callback_data=cb_data))
        keyboard.append(row)
    else:
        # Button mode
        cb_data = f"captcha_{chat.id}_{user.id}_pass"
        keyboard.append([InlineKeyboardButton("Click to verify", callback_data=cb_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        msg = await context.bot.send_message(
            chat.id,
            f"{mention_html(user.id, user.first_name)}, {text}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    except TelegramError:
        return
        
    await db.execute(
        "INSERT INTO captcha_pending (chat_id, user_id, answer, message_id) VALUES (?, ?, ?, ?)",
        (chat.id, user.id, answer, msg.message_id)
    )
    await db.commit()
    
    context.job_queue.run_once(
        captcha_timeout_job,
        timeout,
        data={'chat_id': chat.id, 'user_id': user.id, 'msg_id': msg.message_id},
        name=f"captcha_{chat.id}_{user.id}"
    )

async def captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    parts = data.split('_')
    if len(parts) != 4:
        return
        
    _, chat_id_str, user_id_str, user_answer = parts
    chat_id = int(chat_id_str)
    user_id = int(user_id_str)
    
    if query.from_user.id != user_id:
        await query.answer("This CAPTCHA is not for you!", show_alert=True)
        return
        
    db = context.bot_data["db"]
    
    correct_answer = await db.fetchval(
        "SELECT answer FROM captcha_pending WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id)
    )
    
    if not correct_answer:
        await query.answer("CAPTCHA expired or not found.")
        try:
            await query.message.delete()
        except TelegramError:
            pass
        return
        
    if str(user_answer) == str(correct_answer):
        # Pass
        await db.execute("DELETE FROM captcha_pending WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()
        
        try:
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await query.message.delete()
        except TelegramError:
            pass
            
        await query.answer("Verification successful!")
    else:
        # Fail
        await query.answer("Wrong answer, try again.")


def register(app):
    app.add_handler(CommandHandler("captcha", captcha_toggle), group=0)
    app.add_handler(CommandHandler("captchamode", captchamode_cmd), group=0)
    app.add_handler(CommandHandler("captchatime", captchatime_cmd), group=0)
    app.add_handler(CommandHandler("captchakick", captchakick_cmd), group=0)
    app.add_handler(CommandHandler("setcaptchatext", setcaptchatext_cmd), group=0)
    
    # Group 3 so it runs before greetings in Group 4
    app.add_handler(ChatMemberHandler(new_member_captcha, ChatMemberHandler.CHAT_MEMBER), group=3)
    
    app.add_handler(CallbackQueryHandler(captcha_callback, pattern=r'^captcha_'), group=0)
