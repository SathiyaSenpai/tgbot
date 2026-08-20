"""
Senpai's Bot - Random Chatter
Occasionally sends spontaneous messages to active groups (max 5/day).
"""
import logging
import random
import datetime
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from modules.ai_engine import generate_reply
from config import GIPHY_API_KEY

logger = logging.getLogger(__name__)

# In-memory daily message counter per chat
# { chat_id: {"date": datetime.date, "count": int} }
_daily_counts: dict[int, dict] = {}
MAX_DAILY_MESSAGES = 5


def _get_today_count(chat_id: int) -> int:
    today = datetime.date.today()
    entry = _daily_counts.get(chat_id)
    if not entry or entry["date"] != today:
        _daily_counts[chat_id] = {"date": today, "count": 0}
        return 0
    return entry["count"]


def _increment_count(chat_id: int):
    today = datetime.date.today()
    if chat_id not in _daily_counts or _daily_counts[chat_id]["date"] != today:
        _daily_counts[chat_id] = {"date": today, "count": 1}
    else:
        _daily_counts[chat_id]["count"] += 1


def register(app):
    # Check every 90 minutes. 25% chance to speak each time = ~2-3 per day on average, never more than 5.
    app.job_queue.run_repeating(random_chat_job, interval=90 * 60, first=120)


async def random_chat_job(context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    if not db:
        return

    try:
        rows = await db.fetchall(
            "SELECT chat_id FROM chats WHERE chat_type IN ('group', 'supergroup')"
        )
        if not rows:
            return

        for row in rows:
            chat_id = row["chat_id"] if hasattr(row, "keys") else row[0]

            # Hard cap: never more than MAX_DAILY_MESSAGES per group per day
            if _get_today_count(chat_id) >= MAX_DAILY_MESSAGES:
                continue

            # 20% chance per 90-minute window → roughly 2-3 fires per day
            if random.random() > 0.20:
                continue

            # Build time-aware prompt seed
            hour = datetime.datetime.now().hour
            day = datetime.datetime.now().weekday()

            if 0 <= hour < 5:
                seed = "It's very late at night. You're still awake for no particular reason."
            elif 5 <= hour < 9:
                seed = "Early morning. You're awake but really didn't want to be."
            elif 9 <= hour < 17:
                seed = "Daytime. Nothing special is happening."
            elif 17 <= hour < 21:
                seed = "Evening. Maybe gaming, maybe just chilling."
            else:
                seed = "Night time. You feel like saying something but you're not sure what."

            if day >= 5:
                seed += " It's the weekend."

            try:
                reply_text, send_gif, gif_query = await generate_reply(
                    chat_id=chat_id,
                    user_name="",  # spontaneous, no user to reply to
                    user_text=seed,
                )

                await context.bot.send_message(chat_id=chat_id, text=reply_text)
                _increment_count(chat_id)

                # Very rarely add a GIF to a spontaneous message too (5% chance)
                if send_gif and GIPHY_API_KEY and random.random() < 0.05:
                    from modules.ai_chat import fetch_gif
                    # gif_query already provided by engine
                    gif_url = await fetch_gif(gif_query)
                    if gif_url:
                        await context.bot.send_animation(chat_id=chat_id, animation=gif_url)

            except TelegramError as e:
                logger.warning(f"[Random Chatter] Telegram error for chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"[Random Chatter] Error for chat {chat_id}: {e}")

    except Exception as e:
        logger.error(f"[Random Chatter] Job error: {e}")
