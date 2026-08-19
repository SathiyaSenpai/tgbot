import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

from utils.decorators import admin_required, can_restrict, group_only, invalidate_admin_cache
from utils.helpers import parse_time, get_target_user, mention_html, can_act_on_user

logger = logging.getLogger(__name__)

async def log_action(db, context, chat_id, text):
    log_channel_id = await db.get_chat_setting(chat_id, 'log_channel_id', None)
    if log_channel_id:
        try:
            await context.bot.send_message(chat_id=log_channel_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not send log to {log_channel_id}: {e}")

@group_only
@can_restrict
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Who do you want me to ban, senpai? (・`ω´・) Please specify someone!")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        text = f"Banned {mention_html(target_id, 'User')}."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Ban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Uwaaah~ (╥﹏╥) I couldn't ban them: {e}")

@group_only
@can_restrict
async def sban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
        
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        await log_action(db, context, chat.id, f"<b>Silent Ban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except Exception:
        pass

@group_only
@can_restrict
async def dban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("Senpai, you have to reply to their message so I know who to delete! (｀･ω･´)")
        return
        
    target_id = update.effective_message.reply_to_message.from_user.id
    reason = " ".join(context.args) if context.args else ""
    
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await update.effective_message.reply_to_message.delete()
    except Exception:
        pass
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        text = f"Banned {mention_html(target_id, 'User')} and deleted their message."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>DBan</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Uwaaah~ (╥﹏╥) I couldn't ban them: {e}")

@group_only
@can_restrict
async def tban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, rest = await get_target_user(update, context, return_rest=True)
    if not target_id or not rest:
        await update.effective_message.reply_text("Usage: /tban <user> <time> [reason]")
        return
        
    parts = rest.split(maxsplit=1)
    time_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        await update.effective_message.reply_text("Invalid time format.")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, until_date=until_date, revoke_messages=True)
        text = f"Temporarily banned {mention_html(target_id, 'User')} until {until_date.strftime('%Y-%m-%d %H:%M:%S UTC')}."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Temp Ban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to temp ban: {e}")

@group_only
@can_restrict
async def stban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
        
    target_id, rest = await get_target_user(update, context, return_rest=True)
    if not target_id or not rest:
        return
        
    parts = rest.split(maxsplit=1)
    time_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, until_date=until_date, revoke_messages=True)
        await log_action(db, context, chat.id, f"<b>Silent Temp Ban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except Exception:
        pass

@group_only
@can_restrict
async def dtban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("You need to reply to a message, senpai! (´• ω •`)")
        return
        
    target_id = update.effective_message.reply_to_message.from_user.id
    
    if not context.args:
        await update.effective_message.reply_text("Usage: /dtban <time> [reason] ~ Don't forget the time, senpai! (｡♥‿♥｡)")
        return
        
    time_str = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    
    until_date = parse_time(time_str)
    if not until_date:
        await update.effective_message.reply_text("Invalid time format.")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await update.effective_message.reply_to_message.delete()
    except Exception:
        pass
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, until_date=until_date, revoke_messages=True)
        text = f"Temporarily banned {mention_html(target_id, 'User')} and deleted message."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>D-Temp Ban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nUntil: {until_date}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed: {e}")

@group_only
@can_restrict
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Who is it, senpai? You need to specify a user! (*・ω・)ﾉ")
        return
        
    try:
        await context.bot.unban_chat_member(chat.id, target_id, only_if_banned=True)
        await update.effective_message.reply_text(f"Unbanned {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Unban</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to unban: {e}")

@group_only
@can_restrict
async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Who is it, senpai? You need to specify a user! (*・ω・)ﾉ")
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        await context.bot.unban_chat_member(chat.id, target_id)
        text = f"Kicked {mention_html(target_id, 'User')}."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>Kick</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to kick: {e}")

@group_only
@can_restrict
async def skick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    try:
        await update.effective_message.delete()
    except Exception:
        pass
        
    target_id, reason = await get_target_user(update, context)
    if not target_id:
        return
        
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        return
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        await context.bot.unban_chat_member(chat.id, target_id)
        await log_action(db, context, chat.id, f"<b>Silent Kick</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except Exception:
        pass

@group_only
@can_restrict
async def dkick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("You need to reply to a message, senpai! (´• ω •`)")
        return
        
    target_id = update.effective_message.reply_to_message.from_user.id
    reason = " ".join(context.args) if context.args else ""
    
    if not await can_act_on_user(context, chat.id, user.id, target_id):
        await update.effective_message.reply_text("I-I can't do that to them! (´-﹏-`；) They are too powerful!")
        return
        
    try:
        await update.effective_message.reply_to_message.delete()
    except Exception:
        pass
        
    try:
        await context.bot.ban_chat_member(chat.id, target_id, revoke_messages=True)
        await context.bot.unban_chat_member(chat.id, target_id)
        text = f"Kicked {mention_html(target_id, 'User')} and deleted message."
        if reason:
            text += f"\nReason: {reason}"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
        await log_action(db, context, chat.id, f"<b>DKick</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}\nReason: {reason or 'None'}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed: {e}")

@group_only
@admin_required
async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, title = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
        
    custom_title = title[:16] if title else ""
    
    try:
        await context.bot.promote_chat_member(
            chat.id, target_id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True,
            can_manage_video_chats=True
        )
        if custom_title:
            try:
                await context.bot.set_chat_administrator_custom_title(chat.id, target_id, custom_title)
            except Exception as e:
                logger.warning(f"Could not set title: {e}")
        
        await update.effective_message.reply_text(f"Promoted {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)
        invalidate_admin_cache(chat.id)
        await log_action(db, context, chat.id, f"<b>Promoted</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to promote: {e}")

@group_only
@admin_required
async def demote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = context.bot_data["db"]
    
    target_id, _ = await get_target_user(update, context)
    if not target_id:
        await update.effective_message.reply_text("Specify a user.")
        return
        
    try:
        await context.bot.promote_chat_member(
            chat.id, target_id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_invite_users=False,
            can_manage_video_chats=False,
            can_change_info=False,
            can_manage_chat=False
        )
        await update.effective_message.reply_text(f"Demoted {mention_html(target_id, 'User')}.", parse_mode=ParseMode.HTML)
        invalidate_admin_cache(chat.id)
        await log_action(db, context, chat.id, f"<b>Demoted</b>\nAdmin: {mention_html(user.id, user.first_name)}\nUser: {mention_html(target_id, 'User')}")
    except (TelegramError, BadRequest, Forbidden) as e:
        await update.effective_message.reply_text(f"Failed to demote: {e}")

@group_only
async def adminlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        admins = await chat.get_administrators()
        text = "<b>Admins:</b>\n"
        for a in admins:
            title = a.custom_title or "Admin"
            text += f"• {mention_html(a.user.id, a.user.first_name)} - {title}\n"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.effective_message.reply_text(f"Failed to get adminlist: {e}")

@group_only
@admin_required
async def admincache_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    invalidate_admin_cache(chat.id)
    await update.effective_message.reply_text("Admin cache invalidated.")

@group_only
@admin_required
async def settitle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    target_id, title = await get_target_user(update, context)
    if not target_id or not title:
        await update.effective_message.reply_text("Usage: /settitle <user> <title>")
        return
        
    custom_title = title[:16]
    try:
        await context.bot.set_chat_administrator_custom_title(chat.id, target_id, custom_title)
        await update.effective_message.reply_text(f"Set title for {mention_html(target_id, 'User')} to {custom_title}.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.effective_message.reply_text(f"Failed: {e}")

def register(app):
    app.add_handler(CommandHandler("ban", ban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "ban", ban_user), group=0)
    app.add_handler(CommandHandler("sban", sban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "sban", sban_user), group=0)
    app.add_handler(CommandHandler("dban", dban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "dban", dban_user), group=0)
    app.add_handler(CommandHandler("tban", tban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "tban", tban_user), group=0)
    app.add_handler(CommandHandler("stban", stban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "stban", stban_user), group=0)
    app.add_handler(CommandHandler("dtban", dtban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "dtban", dtban_user), group=0)
    app.add_handler(CommandHandler("unban", unban_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "unban", unban_user), group=0)
    app.add_handler(CommandHandler("kick", kick_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "kick", kick_user), group=0)
    app.add_handler(CommandHandler("skick", skick_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "skick", skick_user), group=0)
    app.add_handler(CommandHandler("dkick", dkick_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "dkick", dkick_user), group=0)
    app.add_handler(CommandHandler("promote", promote_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "promote", promote_user), group=0)
    app.add_handler(CommandHandler("demote", demote_user), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "demote", demote_user), group=0)
    app.add_handler(CommandHandler("adminlist", adminlist_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "adminlist", adminlist_cmd), group=0)
    app.add_handler(CommandHandler("admincache", admincache_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "admincache", admincache_cmd), group=0)
    app.add_handler(CommandHandler("settitle", settitle_cmd), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "settitle", settitle_cmd), group=0)
