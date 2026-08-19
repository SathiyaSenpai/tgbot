import io
import logging
import urllib.parse
import httpx
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


def register(app):
    app.add_handler(CommandHandler(["tr", "tl", "translate"], translate_cmd), group=0)
    app.add_handler(CommandHandler("tts", tts_cmd), group=0)


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Translate text to a target language. Usage: /tr [lang] <text> or reply with /tr [lang]"""
    reply = update.effective_message.reply_to_message
    args = context.args or []

    target_lang = "en"
    text_to_translate = ""

    if reply and (reply.text or reply.caption):
        text_to_translate = reply.text or reply.caption
        if args:
            target_lang = args[0].lower()
    elif args:
        # Check if first arg looks like a language code (2-5 chars)
        if len(args) > 1 and len(args[0]) <= 5 and args[0].isalpha():
            target_lang = args[0].lower()
            text_to_translate = " ".join(args[1:])
        else:
            text_to_translate = " ".join(args)
    else:
        await update.effective_message.reply_text(
            "Usage: Reply to a message with <code>/tr [lang]</code> or send <code>/tr [lang] &lt;text&gt;</code>\n"
            "Default language is English (en).",
            parse_mode=ParseMode.HTML,
        )
        return

    if not text_to_translate.strip():
        await update.effective_message.reply_text("No text found to translate.")
        return

    try:
        encoded = urllib.parse.quote(text_to_translate)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

        if resp.status_code != 200:
            await update.effective_message.reply_text("Translation service unavailable. Please try again.")
            return

        data = resp.json()
        translated = "".join([item[0] for item in data[0] if item[0]])
        src_lang = data[2] if len(data) > 2 else "auto"

        escaped_translation = (
            translated.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        msg = (
            f"🌐 <b>Translation</b> (<code>{src_lang}</code> → <code>{target_lang}</code>):\n\n"
            f"<i>{escaped_translation}</i>"
        )
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.effective_message.reply_text("Failed to translate text.")


async def tts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert text to speech voice note. Usage: /tts [lang] <text> or reply with /tts [lang]"""
    reply = update.effective_message.reply_to_message
    args = context.args or []

    lang = "en"
    text_to_speak = ""

    if reply and (reply.text or reply.caption):
        text_to_speak = reply.text or reply.caption
        if args:
            lang = args[0].lower()
    elif args:
        if len(args) > 1 and len(args[0]) <= 5 and args[0].isalpha():
            lang = args[0].lower()
            text_to_speak = " ".join(args[1:])
        else:
            text_to_speak = " ".join(args)
    else:
        await update.effective_message.reply_text(
            "Usage: Reply to a message with <code>/tts [lang]</code> or send <code>/tts [lang] &lt;text&gt;</code>\n"
            "Default language is English (en). Example: <code>/tts ja konnichiwa</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not text_to_speak.strip():
        await update.effective_message.reply_text("No text found to speak.")
        return

    # Limit text length for TTS to prevent excessive payload
    text_to_speak = text_to_speak[:500]

    try:
        encoded = urllib.parse.quote(text_to_speak)
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded}&tl={lang}&client=tw-ob"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

        if resp.status_code != 200 or not resp.content:
            await update.effective_message.reply_text("TTS service unavailable. Please check the language code.")
            return

        audio_stream = io.BytesIO(resp.content)
        audio_stream.name = "tts.mp3"
        audio_stream.seek(0)

        reply_to_id = reply.message_id if reply else update.effective_message.message_id

        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=audio_stream,
            reply_to_message_id=reply_to_id,
        )

    except Exception as e:
        logger.error(f"TTS error: {e}")
        await update.effective_message.reply_text("Failed to generate speech audio.")
