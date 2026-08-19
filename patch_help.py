import re

with open('modules/start.py', 'r') as f:
    content = f.read()

REPLACE_CODE = '''async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command with optional category argument."""
    if update.effective_chat.type != ChatType.PRIVATE:
        bot = await context.bot.get_me()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Help in PM", url=f"t.me/{bot.username}?start=help")]
        ])
        await update.effective_message.reply_text(
            "Contact me in PM to get help.",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        return
        
    args = context.args'''

content = re.sub(r'async def help_handler.*?args = context\.args', REPLACE_CODE, content, flags=re.DOTALL)

with open('modules/start.py', 'w') as f:
    f.write(content)

