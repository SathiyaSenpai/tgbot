import logging
from telegram import Update, InputProfilePhotoStatic
from telegram.ext import CommandHandler, PrefixHandler, ContextTypes
from telegram.error import TelegramError

from utils.decorators import owner_required

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("setbotname", setbotname), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setbotname", setbotname), group=0)
    app.add_handler(CommandHandler("setbotdesc", setbotdesc), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setbotdesc", setbotdesc), group=0)
    app.add_handler(CommandHandler("setbotshortdesc", setbotshortdesc), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setbotshortdesc", setbotshortdesc), group=0)
    app.add_handler(CommandHandler("setbotphoto", setbotphoto), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "setbotphoto", setbotphoto), group=0)
    app.add_handler(CommandHandler("removebotphoto", removebotphoto), group=0)
    app.add_handler(PrefixHandler(['!', '?'], "removebotphoto", removebotphoto), group=0)

@owner_required
async def setbotname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /setbotname <name>")
        return
        
    name = " ".join(context.args)
    if len(name) > 64:
        await update.effective_message.reply_text("Name is too long (max 64 characters).")
        return
        
    try:
        await context.bot.set_my_name(name=name)
        await update.effective_message.reply_text(f"✅ Bot name successfully updated to: <b>{name}</b>", parse_mode="HTML")
    except TelegramError as e:
        logger.error(f"Error setting bot name: {e}")
        await update.effective_message.reply_text(f"Failed to update bot name: {e}")

@owner_required
async def setbotdesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /setbotdesc <text>")
        return
        
    desc = " ".join(context.args)
    try:
        await context.bot.set_my_description(description=desc)
        await update.effective_message.reply_text("✅ Bot description successfully updated.")
    except TelegramError as e:
        logger.error(f"Error setting bot description: {e}")
        await update.effective_message.reply_text(f"Failed to update description: {e}")

@owner_required
async def setbotshortdesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /setbotshortdesc <text>")
        return
        
    desc = " ".join(context.args)
    try:
        await context.bot.set_my_short_description(short_description=desc)
        await update.effective_message.reply_text("✅ Bot short description successfully updated.")
    except TelegramError as e:
        logger.error(f"Error setting short description: {e}")
        await update.effective_message.reply_text(f"Failed to update short description: {e}")

@owner_required
async def setbotphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message or not msg.reply_to_message.photo:
        await msg.reply_text("Please reply to an image to set it as the bot's profile photo.")
        return
        
    try:
        photo_file = await msg.reply_to_message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        await context.bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=bytes(photo_bytes)))
        await msg.reply_text("✅ Bot profile photo successfully updated.")
    except TelegramError as e:
        logger.error(f"Error setting bot photo: {e}")
        await msg.reply_text(f"Failed to update profile photo: {e}")

@owner_required
async def removebotphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.remove_my_profile_photo()
        await update.effective_message.reply_text("✅ Bot profile photo removed.")
    except TelegramError as e:
        logger.error(f"Error removing bot photo: {e}")
        await update.effective_message.reply_text(f"Failed to remove profile photo: {e}")
