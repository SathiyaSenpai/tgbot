import logging
from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.constants import ParseMode, ChatType
from telegram.error import TelegramError

from utils.decorators import admin_required, is_user_admin
from utils.helpers import parse_time

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("schedule", schedule_message), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "schedule", schedule_message), group=0)
    app.add_handler(CommandHandler("schedules", list_schedules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "schedules", list_schedules), group=0)
    app.add_handler(CommandHandler("cancelschedule", cancel_schedule), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "cancelschedule", cancel_schedule), group=0)

async def resolve_target_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, str]:
    """Resolves the target chat ID. If in PM, uses the connected chat."""
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    
    if update.effective_chat.type == ChatType.PRIVATE:
        row = await db.fetchone("SELECT chat_id FROM connections WHERE user_id = ?", (user_id,))
        if not row:
            await update.effective_message.reply_text("You are not connected to any group. Use the connect button in a group first.")
            return 0, ""
            
        chat_id = row[0]
        if not await is_user_admin(chat_id, user_id, context, update):
            await update.effective_message.reply_text("You must be an admin of the connected group to do this.")
            return 0, ""
            
        try:
            chat = await context.bot.get_chat(chat_id)
            chat_title = f" {chat.title}"
        except:
            chat_title = ""
            
        return chat_id, chat_title
        
    return update.effective_chat.id, ""

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
        
    chat_id, chat_title = await resolve_target_chat(update, context)
    if not chat_id:
        return
        
    db = context.bot_data["db"]
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
            "INSERT INTO scheduled_messages (chat_id, user_id, message_text, send_at, job_id, sent) VALUES (?, ?, ?, datetime(CURRENT_TIMESTAMP, '+' || ? || ' seconds'), ?, 0)",
            (chat_id, user_id, message_text, delay, job.id)
        )
        await db.commit()
        
        await update.effective_message.reply_text(f"✅ Message scheduled to be sent in {time_str}{chat_title}.")
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
    chat_id, chat_title = await resolve_target_chat(update, context)
    if not chat_id:
        return
        
    db = context.bot_data["db"]
    
    try:
        rows = await db.fetchall(
            "SELECT id, send_at, message_text FROM scheduled_messages WHERE chat_id = ? AND sent = 0 ORDER BY send_at",
            (chat_id,)
        )
        
        if not rows:
            await update.effective_message.reply_text(f"No pending scheduled messages for this chat{chat_title}.")
            return
            
        text = f"📅 <b>Scheduled Messages{chat_title}:</b>\n\n"
        for row_id, send_at, msg in rows:
            preview = msg[:30] + "..." if len(msg) > 30 else msg
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
        
    chat_id, chat_title = await resolve_target_chat(update, context)
    if not chat_id:
        return
        
    db = context.bot_data["db"]
    
    try:
        row = await db.fetchone("SELECT job_id FROM scheduled_messages WHERE id = ? AND chat_id = ? AND sent = 0", (schedule_id, chat_id))
        if not row:
            await update.effective_message.reply_text(f"Pending scheduled message not found with that ID in this chat{chat_title}.")
            return
            
        job_id = row[0]
        if job_id:
            for job in context.job_queue.get_jobs_by_name(job_id):
                job.schedule_removal()
        
        await db.execute("UPDATE scheduled_messages SET sent = 2 WHERE id = ?", (schedule_id,))
        await db.commit()
        
        await update.effective_message.reply_text(f"✅ Cancelled scheduled message ID {schedule_id}{chat_title}.")
    except Exception as e:
        logger.error(f"Error cancelling schedule: {e}")
        await update.effective_message.reply_text("Failed to cancel scheduled message.")
