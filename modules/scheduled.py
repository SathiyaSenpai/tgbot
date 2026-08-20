"""
Senpai's Bot - Scheduled Messages
Only works in PM. Schedule commands in groups are silently ignored.
"""
import logging
from telegram import Update
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.constants import ParseMode, ChatType

from utils.decorators import is_user_admin
from utils.helpers import parse_time

logger = logging.getLogger(__name__)


def register(app):
    app.add_handler(CommandHandler("schedule", schedule_message), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "schedule", schedule_message), group=0)
    app.add_handler(CommandHandler("schedules", list_schedules), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "schedules", list_schedules), group=0)
    app.add_handler(CommandHandler("cancelschedule", cancel_schedule), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "cancelschedule", cancel_schedule), group=0)


    # Reload lost scheduled jobs on startup
    app.job_queue.run_once(_reload_schedules_on_startup, 5)


async def _reload_schedules_on_startup(context: ContextTypes.DEFAULT_TYPE):
    import datetime
    db = context.bot_data.get("db")
    if not db:
        return

    try:
        rows = await db.fetchall(
            "SELECT id, chat_id, user_id, message_text, send_at, job_id "
            "FROM scheduled_messages WHERE sent = 0"
        )
        if not rows:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        reloaded = 0

        for row in rows:
            schedule_id = row["id"]
            chat_id = row["chat_id"]
            user_id = row["user_id"]
            message_text = row["message_text"]
            send_at_str = row["send_at"]
            
            try:
                # Parse SQLite datetime string e.g. "2026-08-20 23:45:00"
                send_at = datetime.datetime.strptime(send_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                delay = (send_at - now).total_seconds()
            except Exception as e:
                logger.error(f"Failed to parse time for schedule #{schedule_id}: {e}")
                continue

            if delay <= 0:
                delay = 1  # Send immediately if missed

            new_job = context.job_queue.run_once(
                _send_scheduled_message,
                delay,
                data={"chat_id": chat_id, "text": message_text, "schedule_id": schedule_id},
                name=f"sched_{schedule_id}",
                chat_id=chat_id,
                user_id=user_id
            )
            
            # Update job_id in database since the PTB Job ID has changed
            await db.execute("UPDATE scheduled_messages SET job_id = ? WHERE id = ?", (new_job.id, schedule_id))
            reloaded += 1
            
        await db.commit()
        logger.info(f"[Scheduled] Reloaded {reloaded} pending scheduled messages.")

    except Exception as e:
        logger.error(f"[Scheduled] Failed to reload pending schedules: {e}")


async def _require_pm_with_connection(update: Update, context) -> tuple[int, str]:
    """
    Ensures the command is used only in PM and the user has a connected group.
    Returns (target_chat_id, chat_title) on success, (0, "") on failure.
    """
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "Schedule commands only work in my DMs.\n"
            "Message me privately and use /schedule there."
        )
        return 0, ""

    db = context.bot_data["db"]
    user_id = update.effective_user.id

    row = await db.fetchone("SELECT chat_id FROM connections WHERE user_id = ?", (user_id,))
    if not row:
        await update.effective_message.reply_text(
            "You're not connected to any group.\n"
            "Go to your group and send /connect first, then tap the button."
        )
        return 0, ""

    chat_id = row[0]

    if not await is_user_admin(chat_id, user_id, context, update):
        await update.effective_message.reply_text("You need to be an admin of the connected group to schedule messages.")
        return 0, ""

    try:
        chat = await context.bot.get_chat(chat_id)
        chat_title = chat.title or str(chat_id)
    except Exception:
        chat_title = str(chat_id)

    return chat_id, chat_title


async def schedule_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, chat_title = await _require_pm_with_connection(update, context)
    if not chat_id:
        return

    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /schedule &lt;time&gt; &lt;message&gt;\n"
            "Time format: 5m, 2h, 1d\n\n"
            "Example: /schedule 30m Good morning everyone!",
            parse_mode=ParseMode.HTML
        )
        return

    time_str = context.args[0]
    # Everything after the time argument is the message
    parts = update.effective_message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.effective_message.reply_text("Please include a message to schedule.")
        return

    message_text = parts[2]
    delay = parse_time(time_str)
    if not delay:
        await update.effective_message.reply_text("Invalid time. Use formats like 5m, 2h, 1d.")
        return

    delay_seconds = int(delay.total_seconds())
    db = context.bot_data["db"]
    user_id = update.effective_user.id

    try:
        # We need the ID first, so we insert, then run_once, then update job_id
        cursor = await db.execute(
            "INSERT INTO scheduled_messages (chat_id, user_id, message_text, send_at, job_id, sent) "
            "VALUES (?, ?, ?, datetime(CURRENT_TIMESTAMP, '+' || ? || ' seconds'), ?, 0)",
            (chat_id, user_id, message_text, delay_seconds, "pending"),
        )
        schedule_id = cursor.lastrowid

        job = context.job_queue.run_once(
            _send_scheduled_message,
            delay,
            data={"chat_id": chat_id, "text": message_text, "schedule_id": schedule_id},
            name=f"sched_{schedule_id}",
            chat_id=chat_id,
            user_id=user_id,
        )

        await db.execute("UPDATE scheduled_messages SET job_id = ? WHERE id = ?", (f"sched_{schedule_id}", schedule_id))
        await db.commit()

        await update.effective_message.reply_text(
            f"✅ Scheduled to send in <b>{time_str}</b> → <b>{chat_title}</b>\n\n"
            f"<i>{message_text[:80]}{'...' if len(message_text) > 80 else ''}</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"[Scheduled] Error scheduling: {e}")
        await update.effective_message.reply_text("Something went wrong while scheduling. Try again.")


async def _send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    chat_id = data["chat_id"]
    text = data["text"]
    schedule_id = data.get("schedule_id")
    db = context.bot_data.get("db")

    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        if db:
            if schedule_id:
                await db.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (schedule_id,))
            else:
                await db.execute("UPDATE scheduled_messages SET sent = 1 WHERE job_id = ?", (job.name or job.id,))
            await db.commit()
    except Exception as e:
        logger.error(f"[Scheduled] Failed to deliver message to {chat_id}: {e}")


async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, chat_title = await _require_pm_with_connection(update, context)
    if not chat_id:
        return

    db = context.bot_data["db"]

    try:
        rows = await db.fetchall(
            "SELECT id, send_at, message_text FROM scheduled_messages WHERE chat_id = ? AND sent = 0 ORDER BY send_at",
            (chat_id,),
        )

        if not rows:
            await update.effective_message.reply_text(f"No pending scheduled messages for <b>{chat_title}</b>.", parse_mode=ParseMode.HTML)
            return

        text = f"📅 <b>Scheduled → {chat_title}</b>\n\n"
        for row_id, send_at, msg in rows:
            preview = msg[:40] + "..." if len(msg) > 40 else msg
            text += f"• <code>#{row_id}</code>  ⏰ {send_at}\n  <i>{preview}</i>\n\n"

        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"[Scheduled] Error listing: {e}")
        await update.effective_message.reply_text("Failed to fetch scheduled messages.")


async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id, chat_title = await _require_pm_with_connection(update, context)
    if not chat_id:
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /cancelschedule &lt;id&gt;", parse_mode=ParseMode.HTML)
        return

    try:
        schedule_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("That's not a valid ID. Use the number from /schedules.")
        return

    db = context.bot_data["db"]

    try:
        row = await db.fetchone(
            "SELECT job_id FROM scheduled_messages WHERE id = ? AND chat_id = ? AND sent = 0",
            (schedule_id, chat_id),
        )
        if not row:
            await update.effective_message.reply_text(f"No pending message with ID #{schedule_id} for <b>{chat_title}</b>.", parse_mode=ParseMode.HTML)
            return

        job_name = f"sched_{schedule_id}"
        jobs = context.job_queue.get_jobs_by_name(job_name)
        if not jobs and row[0]:
            jobs = context.job_queue.get_jobs_by_name(row[0])

        for job in jobs:
            job.schedule_removal()

        await db.execute("UPDATE scheduled_messages SET sent = 2 WHERE id = ?", (schedule_id,))
        await db.commit()

        await update.effective_message.reply_text(f"✅ Cancelled message <code>#{schedule_id}</code>.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"[Scheduled] Error cancelling: {e}")
        await update.effective_message.reply_text("Failed to cancel scheduled message.")
