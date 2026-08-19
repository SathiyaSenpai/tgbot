"""
Senpai's Bot - Start & Help Module
Handles /start (with deep-link routing), /help with inline keyboard navigation.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, PrefixHandler,
    CallbackQueryHandler,
    ContextTypes
)
from telegram.constants import ParseMode, ChatType


logger = logging.getLogger(__name__)

# Help categories with their commands
HELP_CATEGORIES = {
    "ai": {
        "title": "AI & Chat",
        "commands": (
            "I don't need commands to talk to you. Just tag me or reply to my messages and I'll respond.\n\n"
            "I also occasionally drop a message in the group when I feel like it."
        ),
    },
    "misc": {
        "title": "Misc & Tools",
        "commands": (
            "/tr - Translate text\n"
            "/tts - Text to speech\n"
            "/id - Get IDs\n"
            "/info - User info\n"
            "/ping - Check if alive"
        ),
    },
    "github": {
        "title": "Commit Tracker",
        "commands": (
            "/addrepo - Track repo\n"
            "/rmrepo - Untrack repo\n"
            "/repos - List tracked\n"
            "/setbranch - Change branch\n"
            "/commits - Fetch commits\n"
            "/trackme - Subscribe to PMs\n"
            "/untrackme - Unsubscribe"
        ),
    },
    "schedule": {
        "title": "Scheduling",
        "commands": (
            "/schedule - Schedule message\n"
            "/schedules - List pending\n"
            "/cancelschedule - Cancel"
        ),
    },
    "settings": {
        "title": "Settings",
        "commands": (
            "/setlog - Set log channel\n"
            "/setbotname - Change name\n"
            "/setbotphoto - Change photo"
        ),
    }
}

def _build_help_keyboard(current: str = None) -> InlineKeyboardMarkup:
    """Build the help navigation keyboard without emojis."""
    keys = list(HELP_CATEGORIES.keys())
    buttons = []
    row = []
    for key in keys:
        cat = HELP_CATEGORIES[key]
        label = cat["title"]
        # Make the button label fit and look clean
        short_label = label[:12] if len(label) > 12 else label
        
        if key == current:
            short_label = f"• {short_label} •"
            
        row.append(InlineKeyboardButton(short_label, callback_data=f"help_{key}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)

    if current:
        buttons.append([InlineKeyboardButton("Back to Menu", callback_data="help_main")])

    return InlineKeyboardMarkup(buttons)


MAIN_HELP_TEXT = (
    "<b>Senpai's Bot</b>\n\n"
    "I hang around in your group and occasionally say things.\n\n"
    "Tag me or reply to my messages to talk.\n"
    "I know a lot about custom ROMs, Magisk, and flashing stuff.\n\n"
    "<i>Tap a category below:</i>"
)


def register(app):
    """Register start and help handlers."""
    app.add_handler(CommandHandler("start", start_handler), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "start", start_handler), group=0)
    app.add_handler(CommandHandler("help", help_handler), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "help", help_handler), group=0)
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help_"), group=0)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with deep-link routing."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    db = context.bot_data["db"]
    args = context.args

    if args:
        payload = args[0]

        # Deep-link: rules_{chat_id}
        if payload.startswith("rules_"):
            try:
                chat_id = int(payload[6:])
                rules = await db.get_chat_setting(chat_id, "rules_text")
                if rules:
                    await update.effective_message.reply_text(
                        f"<b>Group Rules:</b>\n\n{rules}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await update.effective_message.reply_text(
                        "No rules have been set for this group yet."
                    )
            except (ValueError, TypeError):
                await update.effective_message.reply_text("Invalid rules link.")
            return

        # Deep-link: note_{chat_id}_{notename}
        if payload.startswith("note_"):
            parts = payload[5:].split("_", 1)
            if len(parts) == 2:
                try:
                    chat_id = int(parts[0])
                    note_name = parts[1]
                    row = await db.fetchone(
                        "SELECT content, media_type, media_id FROM notes WHERE chat_id = ? AND name = ?",
                        (chat_id, note_name),
                    )
                    if row:
                        content = row[0] or ""
                        media_type = row[1]
                        media_id = row[2]
                        if media_type and media_id:
                            send_func = {
                                "photo": context.bot.send_photo,
                                "video": context.bot.send_video,
                                "document": context.bot.send_document,
                                "animation": context.bot.send_animation,
                                "sticker": context.bot.send_sticker,
                                "voice": context.bot.send_voice,
                                "audio": context.bot.send_audio,
                            }.get(media_type)
                            if send_func:
                                await send_func(
                                    update.effective_chat.id,
                                    media_id,
                                    caption=content if media_type != "sticker" else None,
                                    parse_mode=ParseMode.HTML if content else None,
                                )
                                return
                        if content:
                            from utils.formatting import extract_buttons, apply_fillings
                            content = apply_fillings(content, user=update.effective_user)
                            text, keyboard = extract_buttons(content)
                            await update.effective_message.reply_text(
                                text,
                                parse_mode=ParseMode.HTML,
                                reply_markup=keyboard,
                            )
                    else:
                        await update.effective_message.reply_text("Note not found.")
                except (ValueError, TypeError):
                    await update.effective_message.reply_text("Invalid note link.")
            return

        # Deep-link: connect_{chat_id}
        if payload.startswith("connect_"):
            try:
                chat_id = int(payload[8:])
                from utils.decorators import is_user_admin
                if await is_user_admin(chat_id, update.effective_user.id, context):
                    await db.execute(
                        "INSERT INTO connections (user_id, chat_id) VALUES (?, ?) "
                        "ON CONFLICT(user_id) DO UPDATE SET chat_id = ?",
                        (update.effective_user.id, chat_id, chat_id),
                    )
                    await db.commit()
                    try:
                        chat = await context.bot.get_chat(chat_id)
                        chat_title = chat.title
                    except Exception:
                        chat_title = str(chat_id)
                    await update.effective_message.reply_text(
                        f"Connected to <b>{chat_title}</b>.\n"
                        f"You can now run admin commands here and they'll apply to that group.",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await update.effective_message.reply_text(
                        "You are not an admin in that group."
                    )
            except (ValueError, TypeError):
                await update.effective_message.reply_text("Invalid connect link.")
            return

    # Default /start message
    await update.effective_message.reply_text(
        MAIN_HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_build_help_keyboard(),
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command with optional category argument."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
        
    args = context.args

    if args:
        category = args[0].lower()
        if category in HELP_CATEGORIES:
            cat = HELP_CATEGORIES[category]
            await update.effective_message.reply_text(
                f"<b>{cat['title']}</b>\n\n{cat['commands']}",
                parse_mode=ParseMode.HTML,
            )
            return
        await update.effective_message.reply_text(
            f"Unknown category: {category}\n"
            f"Available: {', '.join(HELP_CATEGORIES.keys())}"
        )
        return

    await update.effective_message.reply_text(
        MAIN_HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_build_help_keyboard(),
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help navigation button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "help_main":
        await query.edit_message_text(
            MAIN_HELP_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=_build_help_keyboard(),
        )
        return

    category = data.replace("help_", "")
    if category in HELP_CATEGORIES:
        cat = HELP_CATEGORIES[category]
        await query.edit_message_text(
            f"<b>{cat['title']}</b>\n\n{cat['commands']}",
            parse_mode=ParseMode.HTML,
            reply_markup=_build_help_keyboard(current=category),
        )
