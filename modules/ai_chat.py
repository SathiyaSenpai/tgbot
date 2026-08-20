"""
Senpai's Bot - AI Chat Handler
Listens for mentions/replies/names and responds using the multi-model AI engine.
Also handles GIF sending via Giphy API.
"""
import logging
import random
import re
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
        logger.warning("[AI Chat] GIPHY_API_KEY not configured — skipping GIF fetch.")
        return None
    try:
        params = {
            "q": query,
            "api_key": GIPHY_API_KEY,
            "limit": 20,
            "rating": "pg-13",
            "lang": "en",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://api.giphy.com/v1/gifs/search", params=params)
        
        if resp.status_code == 200:
            results = resp.json().get("data", [])
            if results:
                # Pick from top 5 results — high relevance, still some variety
                top = results[:5]
                pick = random.choice(top)
                images = pick.get("images", {})
                gif_url = (
                    images.get("downsized_medium", {}).get("url")
                    or images.get("fixed_height", {}).get("url")
                    or images.get("original", {}).get("url")
                    or images.get("original", {}).get("mp4")
                )
                return gif_url
            else:
                logger.warning(f"[AI Chat] Giphy returned 0 results for query '{query}'")
        else:
            logger.error(f"[AI Chat] Giphy API error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"[AI Chat] GIF fetch exception: {e}")
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
        gif_title = msg.animation.file_name or ""
        # Use the filename as a content hint for the LLM — strip extension, humanise
        gif_hint = gif_title.replace("_", " ").replace("-", " ").rsplit(".", 1)[0].strip()
        if gif_hint and len(gif_hint) > 2:
            raw_text += f" [sends a GIF: {gif_hint}]"
        else:
            raw_text += " [sends a GIF]"
    elif msg.sticker:
        emoji = msg.sticker.emoji or ""
        set_name = msg.sticker.set_name or ""
        raw_text += f" [sends a sticker {emoji} from {set_name}]".rstrip("from ")
    elif msg.photo:
        raw_text += " [sends a photo]"

    raw_text = raw_text.strip()
    
    if not raw_text:
        return

    # Check triggers (case-insensitive)
    is_private = update.effective_chat.type == ChatType.PRIVATE
    is_mentioned = bool(bot_username and f"@{bot_username.lower()}" in raw_text.lower())
    is_name_called = "scarlet" in raw_text.lower()
    is_replied_to = bool(
        msg.reply_to_message
        and msg.reply_to_message.from_user
        and msg.reply_to_message.from_user.id == bot_id
    )

    # In groups, only respond if mentioned, replied to, or named
    if not (is_private or is_mentioned or is_name_called or is_replied_to):
        return

    # Clean up username mentions from user text
    user_text = raw_text
    if bot_username:
        # Remove @username case-insensitively
        user_text = re.sub(rf"@{re.escape(bot_username)}", "", user_text, flags=re.IGNORECASE).strip()
    
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
            db=context.bot_data.get("db"),
        )

        if send_gif and GIPHY_API_KEY:
            # GIF-only mode: when replying with a GIF, skip the text entirely
            logger.info(f"[AI Chat] Fetching Giphy GIF for query: '{gif_query}'")
            gif_url = await fetch_gif(gif_query)
            if gif_url:
                try:
                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=gif_url,
                        reply_to_message_id=msg.message_id,
                    )
                    logger.info("[AI Chat] Successfully sent GIF reaction.")
                except Exception as tg_err:
                    logger.error(f"[AI Chat] Telegram send_animation error ({gif_url}): {tg_err}")
                    # GIF failed — fall back to text so the user gets some response
                    if reply_text:
                        await msg.reply_text(reply_text)
            else:
                # Giphy returned nothing — fall back to text
                if reply_text:
                    await msg.reply_text(reply_text)
        else:
            # No GIF — just send the text
            if reply_text:
                await msg.reply_text(reply_text)

    except Exception as e:
        logger.error(f"[AI Chat] Error in handle_chat: {e}", exc_info=True)
