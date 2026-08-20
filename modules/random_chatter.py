"""
Senpai's Bot - Random Chatter
Occasionally sends spontaneous messages to active groups.
"""
import logging
import random
import datetime
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from modules.ai_engine import generate_reply
from config import GIPHY_API_KEY

logger = logging.getLogger(__name__)

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
    # Runs every 90 minutes. ~20% chance to speak = ~2-3 times a day.
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

            if _get_today_count(chat_id) >= MAX_DAILY_MESSAGES:
                continue

            if random.random() > 0.20:
                continue

            hour = datetime.datetime.now().hour
            day = datetime.datetime.now().weekday()
            
            prompts = []
            
            if 0 <= hour < 5:
                prompts = [
                    "complain about being awake at this hour.",
                    "say something about a weird bug you just found in your code.",
                    "drop a random very tired thought.",
                    "just sigh or say something short indicating you need sleep.",
                ]
            elif 5 <= hour < 9:
                prompts = [
                    "complain that it's too early.",
                    "say something about needing coffee or energy.",
                    "drop a grumpy morning observation.",
                ]
            elif 9 <= hour < 17:
                prompts = [
                    "say you're bored.",
                    "mention compiling a kernel or flashing a ROM.",
                    "drop a random dry observation about nothing.",
                    "mention an obscure underground song you're listening to.",
                ]
            elif 17 <= hour < 21:
                prompts = [
                    "say something about gaming.",
                    "complain that you're hungry but don't want to get up.",
                    "ask a random rhetorical question.",
                ]
            else:
                prompts = [
                    "say a random late night thought.",
                    "complain about someone breaking their device.",
                    "just send a single dry word or 'hmm'.",
                ]

            prompt_choice = random.choice(prompts)
            if day >= 5:
                prompt_choice += " (Context: It's the weekend.)"
            
            seed = f"[System Instruction: You are bored. Spontaneously speak to the group without being spoken to. {prompt_choice}]"

            try:
                reply_text, send_gif, gif_query = await generate_reply(
                    chat_id=chat_id,
                    user_name="System",
                    user_text=seed,
                )

                await context.bot.send_message(chat_id=chat_id, text=reply_text)
                _increment_count(chat_id)

                # Very rarely add a GIF to a spontaneous message
                if send_gif and GIPHY_API_KEY and random.random() < 0.10:
                    from modules.ai_chat import fetch_gif
                    gif_url = await fetch_gif(gif_query)
                    if gif_url:
                        await context.bot.send_animation(chat_id=chat_id, animation=gif_url)

            except TelegramError as e:
                logger.warning(f"[Random Chatter] Telegram error for chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"[Random Chatter] Error for chat {chat_id}: {e}")

    except Exception as e:
        logger.error(f"[Random Chatter] Job error: {e}")
