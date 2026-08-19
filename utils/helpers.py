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
        reason = " ".join(args) if args else None
    elif args:
        first_arg = args[0]

        if USER_ID_REGEX.match(first_arg):
            user_id = int(first_arg)
            reason = " ".join(args[1:]) if len(args) > 1 else None
        elif USERNAME_REGEX.match(first_arg):
            first_arg.lstrip("@")
            reason = " ".join(args[1:]) if len(args) > 1 else None
            return None, reason, None  # Will need to handle via @username
        else:
            reason = " ".join(args)

    if user_id and not user_obj:
        try:
            chat = message.chat
            member = await context.bot.get_chat_member(chat.id, user_id)
            user_obj = member.user
        except Exception:
            pass

    return user_id, reason, user_obj


async def get_target_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, return_rest: bool = False
) -> Tuple[Optional[int], Optional[str]]:
    message = update.effective_message
    args = context.args or []

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        rest = " ".join(args) if args else None
        return target.id, rest

    if not args:
        return None, None

    first_arg = args[0]
    rest = " ".join(args[1:]) if len(args) > 1 else None

    if USER_ID_REGEX.match(first_arg):
        user_id = int(first_arg)
        return user_id, rest

    if USERNAME_REGEX.match(first_arg):
        username = first_arg.lstrip("@").lower()
        db = context.bot_data.get("db")
        if db:
            row = await db.fetchone("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,))
            if row:
                return row["user_id"], rest
        return None, rest

    if return_rest:
        return None, " ".join(args)

    return None, None

    first_arg = args[0]
    rest = " ".join(args[1:]) if len(args) > 1 else None

    if USER_ID_REGEX.match(first_arg):
        user_id = int(first_arg)
        return user_id, rest

    if USERNAME_REGEX.match(first_arg):
        # Username resolution needs cache, for now return None to prompt failure
        return None, rest

    if return_rest:
        return None, " ".join(args)

    return None, None


async def is_user_in_chat(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
    except Exception:
        return False


async def can_act_on_user(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    target_id: int,
) -> bool:
    bot_id = context.bot.id

    if target_id == bot_id:
        return False

    if target_id == user_id:
        return False

    try:
        target_member = await context.bot.get_chat_member(chat_id, target_id)
        if target_member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return False
    except Exception:
        # If user is not in chat, action (like ban/unban) might still be permitted
        pass

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
