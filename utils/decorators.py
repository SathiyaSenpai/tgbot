"""
Senpai's Bot - Permission Decorators
Wraps handler functions with admin/permission checks.
"""
import logging
import time
from functools import wraps
from typing import Callable, Optional
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from telegram.constants import ChatType, ChatMemberStatus
from config import OWNER_ID

logger = logging.getLogger(__name__)

# Admin cache: {chat_id: {"admins": set(), "ts": timestamp}}
_admin_cache: dict = {}
ADMIN_CACHE_TTL = 300  # 5 minutes


async def _get_admin_ids(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> set:
    now = time.time()
    cached = _admin_cache.get(chat_id)
    if cached and (now - cached["ts"]) < ADMIN_CACHE_TTL:
        return cached["admins"]

    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = {a.user.id for a in admins}
        _admin_cache[chat_id] = {"admins": admin_ids, "ts": now}
        return admin_ids
    except Exception as e:
        logger.error(f"Failed to get admins for {chat_id}: {e}")
        if cached:
            return cached["admins"]
        return set()


def invalidate_admin_cache(chat_id: int) -> None:
    _admin_cache.pop(chat_id, None)


async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id == OWNER_ID:
        return True
    admin_ids = await _get_admin_ids(chat_id, context)
    return user_id in admin_ids


async def is_user_owner(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def get_bot_permissions(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> Optional[ChatMember]:
    try:
        return await context.bot.get_chat_member(chat_id, context.bot.id)
    except Exception as e:
        logger.error(f"Failed to get bot permissions in {chat_id}: {e}")
        return None


def admin_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id
        if not await is_user_admin(update.effective_chat.id, user_id, context):
            await update.effective_message.reply_text("❌ You need to be an admin to use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def owner_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
            if update.effective_user.id != OWNER_ID:
                await update.effective_message.reply_text("❌ Only the bot owner can use this command.")
                return
            return await func(update, context, *args, **kwargs)

        user_id = update.effective_user.id
        if not await is_user_owner(update.effective_chat.id, user_id, context):
            await update.effective_message.reply_text("❌ Only the group owner can use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def can_restrict(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user_id = update.effective_user.id
        if not await is_user_admin(chat.id, user_id, context):
            await update.effective_message.reply_text("❌ You need to be an admin to use this command.")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member or not (
            bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_restrict_members
        ):
            await update.effective_message.reply_text(
                "❌ I need 'Restrict Members' admin permission to do this."
            )
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def can_delete(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user_id = update.effective_user.id
        if not await is_user_admin(chat.id, user_id, context):
            await update.effective_message.reply_text("❌ You need to be an admin to use this command.")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member or not (
            bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_delete_messages
        ):
            await update.effective_message.reply_text(
                "❌ I need 'Delete Messages' admin permission to do this."
            )
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def can_pin(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user_id = update.effective_user.id
        if not await is_user_admin(chat.id, user_id, context):
            await update.effective_message.reply_text("❌ You need to be an admin to use this command.")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member or not (
            bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_pin_messages
        ):
            await update.effective_message.reply_text(
                "❌ I need 'Pin Messages' admin permission to do this."
            )
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def private_only(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            await update.effective_message.reply_text("❌ This command only works in private chat.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def group_only(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            await update.effective_message.reply_text("❌ This command only works in groups.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
