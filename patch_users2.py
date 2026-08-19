import re

with open('modules/commandcontrol.py', 'r') as f:
    content = f.read()

AGGRESSIVE_CACHE_MIDDLEWARE = '''
async def user_cache_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    if not db:
        return

    users_to_cache = []
    
    if update.effective_user:
        users_to_cache.append(update.effective_user)
        
    if update.effective_message:
        msg = update.effective_message
        if msg.reply_to_message and msg.reply_to_message.from_user:
            users_to_cache.append(msg.reply_to_message.from_user)
        if msg.new_chat_members:
            users_to_cache.extend(msg.new_chat_members)
        if msg.left_chat_member:
            users_to_cache.append(msg.left_chat_member)
        if msg.forward_from:
            users_to_cache.append(msg.forward_from)
            
    if update.chat_member:
        if update.chat_member.new_chat_member and update.chat_member.new_chat_member.user:
            users_to_cache.append(update.chat_member.new_chat_member.user)
            
    for u in users_to_cache:
        if u and getattr(u, 'id', None):
            try:
                await db.ensure_user(u.id, u.username, u.first_name, u.last_name)
            except Exception:
                pass
'''

# We need to replace the old user_cache_middleware
content = re.sub(r'async def user_cache_middleware.*?await db\.ensure_user\(user\.id, user\.username, user\.first_name, user\.last_name\)', AGGRESSIVE_CACHE_MIDDLEWARE.strip(), content, flags=re.DOTALL)

with open('modules/commandcontrol.py', 'w') as f:
    f.write(content)
