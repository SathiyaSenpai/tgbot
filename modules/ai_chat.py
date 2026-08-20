"""
Senpai's Bot - AI Chat Handler
Listens for mentions/replies and responds using the multi-model AI engine.
Also handles GIF sending via Tenor API.
"""
import logging
import random
import httpx
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

from config import GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, GIPHY_API_KEY
from modules.ai_engine import (
    init_gemini, init_groq, init_openrouter,
    generate_reply
)

logger = logging.getLogger(__name__)

# Initialize all available providers at module load time
if GEMINI_API_KEY:
    init_gemini(GEMINI_API_KEY)
else:
    logger.warning("[AI Chat] GEMINI_API_KEY not set — Gemini provider disabled.")

if GROQ_API_KEY:
    init_groq(GROQ_API_KEY)
else:
    logger.warning("[AI Chat] GROQ_API_KEY not set — Groq provider disabled.")

if OPENROUTER_API_KEY:
    init_openrouter(OPENROUTER_API_KEY)
else:
    logger.warning("[AI Chat] OPENROUTER_API_KEY not set — OpenRouter provider disabled.")


def register(app):
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.ANIMATION | filters.Sticker.ALL | filters.PHOTO) & ~filters.COMMAND, 
            handle_chat
        ),
        group=5,
    )


async def fetch_gif(query: str) -> str | None:
    """Fetch a contextually appropriate GIF URL from Giphy."""
    if not GIPHY_API_KEY:
        return None
    try:
        params = {
            "q": query,
            "api_key": GIPHY_API_KEY,
            "limit": 15,
            "rating": "pg-13"
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.giphy.com/v1/gifs/search", params=params)
        if resp.status_code == 200:
            results = resp.json().get("data", [])
            if results:
                pick = random.choice(results)
                gif_url = pick.get("images", {}).get("original", {}).get("url")
                return gif_url
    except Exception as e:
        logger.error(f"[AI Chat] GIF fetch error: {e}")
    return None


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    bot_id = context.bot.id
    bot_username = context.bot.username or ""

    # Determine text content based on message type
    raw_text = msg.text or msg.caption or ""
    
    if msg.animation:
        raw_text += " [sends a GIF]"
    elif msg.sticker:
        emoji = msg.sticker.emoji or ""
        raw_text += f" [sends a sticker {emoji}]"
    elif msg.photo:
        raw_text += " [sends a photo]"

    raw_text = raw_text.strip()
    
    if not raw_text:
        return

    # Determine if this message is directed at the bot
    is_mentioned = f"@{bot_username}" in raw_text
    is_replied_to = (
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == bot_id
    )
    is_private = update.effective_chat.type == ChatType.PRIVATE

    if not (is_mentioned or is_replied_to or is_private):
        return

    # Clean up the message text
    user_text = raw_text.replace(f"@{bot_username}", "").strip()
    if not user_text:
        user_text = "hey"

    user_name = update.effective_user.first_name or "someone"
    chat_id = update.effective_chat.id

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        reply_text, send_gif, gif_query = await generate_reply(
            chat_id=chat_id,
            user_name=user_name,
            user_text=user_text,
        )

        # Send the text reply
        await msg.reply_text(reply_text)

        # Optionally send a contextually relevant GIF
        if send_gif:
            if not GIPHY_API_KEY:
                logger.error("[AI Chat] Wanted to send GIF, but GIPHY_API_KEY is missing!")
            else:
                logger.info(f"[AI Chat] Fetching GIF for query: '{gif_query}'")
                gif_url = await fetch_gif(gif_query)
                if gif_url:
                    logger.info(f"[AI Chat] Successfully fetched GIF: {gif_url}")
                    try:
                        await context.bot.send_animation(
                            chat_id=chat_id,
                            animation=gif_url,
                            reply_to_message_id=msg.message_id,
                        )
                        logger.info("[AI Chat] Successfully sent GIF to Telegram.")
                    except Exception as tg_err:
                        logger.error(f"[AI Chat] Telegram failed to send GIF ({gif_url}): {tg_err}")
                else:
                    logger.error(f"[AI Chat] fetch_gif returned None for query '{gif_query}'")

    except Exception as e:
        logger.error(f"[AI Chat] Unexpected error in handle_chat: {e}")
        # Silent fail — no user-facing error message
