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


