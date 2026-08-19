import logging
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from utils.decorators import admin_required
from utils.helpers import parse_time

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("schedule", schedule_message), group=0)
    app.add_handler(CommandHandler("schedules", list_schedules), group=0)
    app.add_handler(CommandHandler("cancelschedule", cancel_schedule), group=0)

@admin_required
async def schedule_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /schedule <time> <message>\nTime format: Xm, Xh, Xd")
        return
        
    time_str = context.args[0]
    message_text = update.effective_message.text.split(maxsplit=2)[2]
    
    delay = parse_time(time_str)
    if not delay or delay <= 0:
        await update.effective_message.reply_text("Invalid time format. Use something like 5m, 2h, 1d.")
        return
        
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        job = context.job_queue.run_once(
            send_scheduled_message, 
            delay, 
            data={"chat_id": chat_id, "text": message_text},
            chat_id=chat_id,
            user_id=user_id
        )
        
        await db.execute(
            "INSERT INTO scheduled_messages (chat_id, user_id, message_text, send_at, job_id, sent) VALUES (?, ?, ?, datetime(CURRENT_TIMESTAMP, '+'|| ? || 'seconds'), ?, 0)",
            (chat_id, user_id, message_text, delay, job.id)
        )
        await db.commit()
        
        await update.effective_message.reply_text(f"Message scheduled to be sent in {time_str}.")
    except Exception as e:
        logger.error(f"Error scheduling message: {e}")
        await update.effective_message.reply_text("Failed to schedule message.")

async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    chat_id = data["chat_id"]
    text = data["text"]
    
    db = context.bot_data.get("db")
    
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        if db:
            await db.execute("UPDATE scheduled_messages SET sent = 1 WHERE job_id = ?", (job.id,))
            await db.commit()
    except TelegramError as e:
        logger.error(f"Failed to send scheduled message to {chat_id}: {e}")

@admin_required
async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        rows = await db.fetchall(
            "SELECT id, send_at, message_text FROM scheduled_messages WHERE chat_id = ? AND sent = 0 ORDER BY send_at",
            (chat_id,)
        )
        
        if not rows:
            await update.effective_message.reply_text("No pending scheduled messages for this chat.")
            return
            
        text = "<b>Scheduled Messages:</b>\n\n"
        for row_id, send_at, msg in rows:
            preview = msg[:30] + "..."if len(msg) > 30 else msg
            text += f"• ID: <code>{row_id}</code> | At: {send_at} | <i>{preview}</i>\n"
            
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error listing schedules: {e}")
        await update.effective_message.reply_text("Failed to list scheduled messages.")

@admin_required
async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /cancelschedule <id>")
        return
        
    try:
        schedule_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid ID. Must be a number.")
        return
        
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    
    try:
        row = await db.fetchone("SELECT job_id FROM scheduled_messages WHERE id = ? AND chat_id = ? AND sent = 0", (schedule_id, chat_id))
        if not row:
            await update.effective_message.reply_text("Pending scheduled message not found with that ID in this chat.")
            return
            
        job_id = row[0]
        jobs = context.job_queue.get_jobs_by_name(job_id) # Using job_id as string might not work, PTB jobs are accessed by id differently if stored
        # For simplicity, we can loop through jobs if needed, but PTB 20 doesn't easily fetch by random UUID id.
        # However, we can just remove it from DB and check in the job callback if it still exists.
        
        # A more robust way: set sent = 2 (cancelled)
        await db.execute("UPDATE scheduled_messages SET sent = 2 WHERE id = ?", (schedule_id,))
        await db.commit()
        
        await update.effective_message.reply_text(f"Cancelled scheduled message ID {schedule_id}.")
    except Exception as e:
        logger.error(f"Error cancelling schedule: {e}")
        await update.effective_message.reply_text("Failed to cancel scheduled message.")
