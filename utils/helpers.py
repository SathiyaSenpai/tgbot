"""
Senpai's Bot - Helper Utilities
Common functions for parsing time, resolving users, formatting, etc.
"""
import re
import logging
from datetime import timedelta
from typing import Optional, Tuple
from telegram import Update, Message, User
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

# Time parsing regex: matches "5m", "2h", "3d", "1w"
TIME_REGEX = re.compile(r"^(\d+)([mhdw])$", re.IGNORECASE)

# User mention/ID regex
USER_ID_REGEX = re.compile(r"^(\d+)$")
USERNAME_REGEX = re.compile(r"^@?([a-zA-Z][a-zA-Z0-9_]{4,31})$")


def parse_time(text: str) -> Optional[timedelta]:
    if not text:
        return None
    match = TIME_REGEX.match(text.strip())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if amount <= 0:
        return None

    units = {
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
        "w": timedelta(weeks=amount),
    }
    return units.get(unit)


def mention_html(user_id: int, name: str) -> str:
    safe_name = (name or "User").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def user_mention(user: User) -> str:
    return mention_html(user.id, user.first_name)


async def extract_user_and_reason(
    message: Message, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[Optional[int], Optional[str], Optional[User]]:
    user_id = None
    reason = None
    user_obj = None
    args = context.args or []

    if message.reply_to_message and message.reply_to_message.from_user:
        user_obj = message.reply_to_message.from_user
        user_id = user_obj.id
        reason = "".join(args) if args else None
    elif args:
        first_arg = args[0]

        if USER_ID_REGEX.match(first_arg):
            user_id = int(first_arg)
            reason = "".join(args[1:]) if len(args) > 1 else None
        elif USERNAME_REGEX.match(first_arg):
            username = first_arg.lstrip("@")
            reason = "".join(args[1:]) if len(args) > 1 else None
            return None, reason, None  # Will need to handle via @username
        else:
            reason = "".join(args)

    if user_id and not user_obj:
        try:
            chat = message.chat
            member = await context.bot.get_chat_member(chat.id, user_id)
            user_obj = member.user
        except Exception:
            pass

    return user_id, reason, user_obj


async def get_target_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    message = update.effective_message
    args = context.args or []

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        reason = "".join(args) if args else None
        return target.id, reason, target.first_name

    if not args:
        return None, None, None

    first_arg = args[0]
    reason = "".join(args[1:]) if len(args) > 1 else None

    if USER_ID_REGEX.match(first_arg):
        user_id = int(first_arg)
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            return user_id, reason, member.user.first_name
        except Exception:
            return user_id, reason, str(user_id)

    if USERNAME_REGEX.match(first_arg):
        username = first_arg.lstrip("@")
        # Can't directly resolve username to user_id via Bot API without the user being in chat
        return None, reason, username

    return None, "".join(args), None


async def is_user_in_chat(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
    except Exception:
        return False


async def can_act_on_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int
) -> bool:
    chat_id = update.effective_chat.id
    bot_id = context.bot.id

    if target_id == bot_id:
        await update.effective_message.reply_text("I'm not going to do that to myself!")
        return False

    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
    except BadRequest:
        return True  # User not in chat, might still be actionable

    if target_member.status == ChatMemberStatus.OWNER:
        await update.effective_message.reply_text("I can't do that to the chat owner.")
        return False

    if target_member.status == ChatMemberStatus.ADMINISTRATOR:
        await update.effective_message.reply_text("I can't do that to another admin.")
        return False

    return True


def format_duration(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} second(s)"
    elif total_seconds < 3600:
        return f"{total_seconds // 60} minute(s)"
    elif total_seconds < 86400:
        return f"{total_seconds // 3600} hour(s)"
    else:
        return f"{total_seconds // 86400} day(s)"


def truncate(text: str, max_len: int = 4000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
