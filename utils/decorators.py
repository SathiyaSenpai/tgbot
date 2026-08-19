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
        # Always include anonymous admin bot ID and channel bot ID
        admin_ids.add(1087968824)  # @GroupAnonymousBot
        admin_ids.add(136817688)   # @Channel_Bot
        _admin_cache[chat_id] = {"admins": admin_ids, "ts": now}
        return admin_ids
    except Exception as e:
        logger.debug(f"Failed to get admins for {chat_id}: {e}")
        if cached:
            return cached["admins"]
        return set()


def invalidate_admin_cache(arg1, arg2=None) -> None:
    chat_id = arg2 if arg2 is not None else arg1
    if isinstance(chat_id, int):
        _admin_cache.pop(chat_id, None)


async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, update: Optional[Update] = None) -> bool:
    if user_id == OWNER_ID:
        return True
    if user_id in (1087968824, 136817688):
        return True
    if update and update.effective_message and update.effective_message.sender_chat:
        if update.effective_message.sender_chat.id == chat_id:
            return True

    admin_ids = await _get_admin_ids(chat_id, context)
    if user_id in admin_ids:
        return True

    # Fallback direct get_chat_member check
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            if chat_id in _admin_cache:
                _admin_cache[chat_id]["admins"].add(user_id)
            return True
    except Exception:
        pass

    return False


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
        logger.debug(f"Failed to get bot permissions in {chat_id}: {e}")
        return None


def admin_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
            return await func(update, context, *args, **kwargs)

        user = update.effective_user
        user_id = user.id if user else 0
        if not await is_user_admin(update.effective_chat.id, user_id, context, update):
            await update.effective_message.reply_text("B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def owner_required(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
            if update.effective_user and update.effective_user.id != OWNER_ID:
                await update.effective_message.reply_text("Gomen nasai! (｡>﹏<｡) Only my master can use this command!")
                return
            return await func(update, context, *args, **kwargs)

        user = update.effective_user
        user_id = user.id if user else 0
        if user_id != OWNER_ID and not await is_user_owner(update.effective_chat.id, user_id, context):
            await update.effective_message.reply_text("Eeeh?! (・_・;) Only the group owner can tell me to do that!")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def can_restrict(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user = update.effective_user
        user_id = user.id if user else 0
        if not await is_user_admin(chat.id, user_id, context, update):
            await update.effective_message.reply_text("B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member:
            await update.effective_message.reply_text("Uwah~ (╥﹏╥) I couldn't check my permissions... something went wrong!")
            return

        if bot_member.status == ChatMemberStatus.OWNER:
            return await func(update, context, *args, **kwargs)
        elif bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            if not getattr(bot_member, 'can_restrict_members', False):
                await update.effective_message.reply_text(
                    "Gomen, senpai~ (╥﹏╥) I need the 'Restrict Members' permission to do this! Please give it to me~"
                )
                return
        else:
            await update.effective_message.reply_text("E-eh?! (O_O) I need to be an admin first before I can help you with that!")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def can_delete(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user = update.effective_user
        user_id = user.id if user else 0
        if not await is_user_admin(chat.id, user_id, context, update):
            await update.effective_message.reply_text("B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member:
            await update.effective_message.reply_text("Uwah~ (╥﹏╥) I couldn't check my permissions... something went wrong!")
            return

        if bot_member.status == ChatMemberStatus.OWNER:
            return await func(update, context, *args, **kwargs)
        elif bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            if not getattr(bot_member, 'can_delete_messages', False):
                await update.effective_message.reply_text(
                    "Senpai... (｡•́︿•̀｡) I can't delete messages without the 'Delete Messages' permission!"
                )
                return
        else:
            await update.effective_message.reply_text("E-eh?! (O_O) I need to be an admin first before I can help you with that!")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def can_pin(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        user = update.effective_user
        user_id = user.id if user else 0
        if not await is_user_admin(chat.id, user_id, context, update):
            await update.effective_message.reply_text("B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~")
            return

        bot_member = await get_bot_permissions(chat.id, context)
        if not bot_member:
            await update.effective_message.reply_text("Uwah~ (╥﹏╥) I couldn't check my permissions... something went wrong!")
            return

        if bot_member.status == ChatMemberStatus.OWNER:
            return await func(update, context, *args, **kwargs)
        elif bot_member.status == ChatMemberStatus.ADMINISTRATOR:
            if not getattr(bot_member, 'can_pin_messages', False):
                await update.effective_message.reply_text(
                    "I can't pin anything! (ノ﹏ヽ) I need the 'Pin Messages' permission, senpai~"
                )
                return
        else:
            await update.effective_message.reply_text("E-eh?! (O_O) I need to be an admin first before I can help you with that!")
            return

        return await func(update, context, *args, **kwargs)
    return wrapper


def private_only(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            await update.effective_message.reply_text("Kyaa! (⁄ ⁄•⁄ω⁄•⁄ ⁄) Let's do this in a private chat, okay?")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def group_only(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            await update.effective_message.reply_text("Senpai~ this command is only for groups! (´• ω •`)")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
