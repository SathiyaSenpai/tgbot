import re

with open('modules/start.py', 'r') as f:
    content = f.read()

# We want to change the part inside help_handler that replies with a button to just `return`
REPLACE_CODE = '''async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command with optional category argument."""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
        
    args = context.args'''

content = re.sub(r'async def help_handler.*?args = context\.args', REPLACE_CODE, content, flags=re.DOTALL)

with open('modules/start.py', 'w') as f:
    f.write(content)

