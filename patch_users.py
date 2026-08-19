import re

with open('modules/commandcontrol.py', 'r') as f:
    content = f.read()

USER_CACHE_MIDDLEWARE = '''
async def user_cache_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = context.bot_data.get("db")
    if user and db:
        await db.ensure_user(user.id, user.username, user.first_name, user.last_name)
'''

# Add the function
content = content.replace("async def check_disabled_middleware", USER_CACHE_MIDDLEWARE + "\n\nasync def check_disabled_middleware")

# Add the handler to register()
# app.add_handler(TypeHandler(Update, user_cache_middleware), group=-3)
REGISTRATION = '''
    # Group -3 for user caching
    from telegram.ext import TypeHandler
    app.add_handler(TypeHandler(Update, user_cache_middleware), group=-3)
'''

content = content.replace("    # Group -2 for middleware", REGISTRATION + "\n    # Group -2 for middleware")

with open('modules/commandcontrol.py', 'w') as f:
    f.write(content)
