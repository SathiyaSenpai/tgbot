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
    "admin": {
        "title": "Admin Commands",
        "commands": (
            "/ban - Ban a user\n"
            "/sban - Silent ban\n"
            "/dban - Ban + delete message\n"
            "/tban - Temporary ban\n"
            "/unban - Unban user\n"
            "/kick - Kick user\n"
            "/skick - Silent kick\n"
            "/dkick - Kick + delete msg\n"
            "/promote - Promote to admin\n"
            "/demote - Remove admin\n"
            "/adminlist - List admins\n"
            "/settitle - Set admin title\n"
            "/admincache - Refresh admin cache"
        ),
    },
    "mute": {
        "title": "Mute Commands",
        "commands": (
            "/mute - Mute user\n"
            "/smute - Silent mute\n"
            "/dmute - Mute + delete msg\n"
            "/tmute - Temporary mute\n"
            "/unmute - Unmute user"
        ),
    },
    "warn": {
        "title": "Warning Commands",
        "commands": (
            "/warn - Warn user\n"
            "/dwarn - Warn + delete msg\n"
            "/swarn - Silent warn\n"
            "/warns - Check warnings\n"
            "/rmwarn - Remove last warning\n"
            "/resetwarn - Reset warnings\n"
            "/warnlimit - Set max warnings\n"
            "/warnmode - Set punishment"
        ),
    },
    "blocklist": {
        "title": "Blocklist",
        "commands": (
            "/addblocklist - Add trigger\n"
            "/rmblocklist - Remove trigger\n"
            "/blocklist - List triggers\n"
            "/blocklistmode - Set action\n"
            "/blocklistdelete - Toggle deletion"
        ),
    },
    "filters": {
        "title": "Filters",
        "commands": (
            "/filter - Set filter\n"
            "/filters - List filters\n"
            "/stop - Remove filter\n"
            "/stopall - Remove all"
        ),
    },
    "notes": {
        "title": "Notes",
        "commands": (
            "/save - Save note\n"
            "/get or #name - Get note\n"
            "/notes - List notes\n"
            "/clear - Delete note\n"
            "/privatenotes - PM toggle"
        ),
    },
    "welcome": {
        "title": "Greetings",
        "commands": (
            "/welcome - Toggle welcome\n"
            "/setwelcome - Set message\n"
            "/goodbye - Toggle goodbye\n"
            "/setgoodbye - Set message\n"
            "/cleanwelcome - Clean old welcomes\n"
            "/cleanservice - Clean join/leave msgs"
        ),
    },
    "rules": {
        "title": "Rules",
        "commands": (
            "/rules - View rules\n"
            "/setrules - Set rules\n"
            "/clearrules - Clear rules\n"
            "/privaterules - PM toggle\n"
            "/setrulesbutton - Custom button text"
        ),
    },
    "pins": {
        "title": "Pins",
        "commands": (
            "/pin - Pin message\n"
            "/unpin - Unpin message\n"
            "/unpinall - Unpin all\n"
            "/pinned - Get pinned msg\n"
            "/permapin - Bot creates & pins"
        ),
    },
    "purge": {
        "title": "Purge",
        "commands": (
            "/purge - Delete messages\n"
            "/spurge - Silent purge\n"
            "/del - Delete one message"
        ),
    },
    "misc": {
        "title": "Misc & Tools",
        "commands": (
            "/tr - Translate text\n"
            "/tts - Text to speech\n"
            "/id - Get IDs\n"
            "/info - User info\n"
            "/ping - Check if alive\n"
            "/kickme - Kick yourself\n"
            "/bam - Fake ban"
        ),
    },
    "flood": {
        "title": "Antiflood",
        "commands": (
            "/flood - Show settings\n"
            "/setflood - Set limit\n"
            "/setfloodmode - Set action"
        ),
    },
    "locks": {
        "title": "Locks",
        "commands": (
            "/lock - Lock type\n"
            "/unlock - Unlock type\n"
            "/locks - Show locks\n"
            "/locktypes - List types"
        ),
    },
    "captcha": {
        "title": "CAPTCHA",
        "commands": (
            "/captcha - Toggle CAPTCHA\n"
            "/captchamode - Set mode\n"
            "/captchatime - Set timeout\n"
            "/captchakick - Kick on fail"
        ),
    },
    "connect": {
        "title": "Connection",
        "commands": (
            "/connect - Connect to group\n"
            "/disconnect - Disconnect\n"
            "/connection - Show connection"
        ),
    },
    "approve": {
        "title": "Approvals",
        "commands": (
            "/approve - Approve user\n"
            "/unapprove - Remove approval\n"
            "/approved - List approved\n"
            "/approval - Check user"
        ),
    },
    "commits": {
        "title": "Commit Tracker",
        "commands": (
            "/addrepo - Track repo\n"
            "/rmrepo - Untrack repo\n"
            "/repos - List tracked\n"
            "/setbranch - Change branch\n"
            "/commits - Fetch commits\n"
            "/trackme - Subscribe\n"
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
            "/disable - Disable command\n"
            "/enable - Enable command\n"
            "/disabled - List disabled\n"
            "/setlog - Set log channel\n"
            "/reports - Toggle reports\n"
            "/setbotname - Change name (owner)\n"
            "/setbotphoto - Change photo (owner)"
        ),
    },
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
    "<b>Hi! I'm Senpai's Bot</b>\n\n"
    "I'm a group management bot with commit tracking features.\n\n"
    "🔹 <b>Add me to your group</b> as admin with full permissions\n"
    "🔹 Use the buttons below to explore commands\n"
    "🔹 Use /help &lt;category&gt; for quick text help\n\n"
    "<i>Tap a category below to see its commands:</i>"
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
