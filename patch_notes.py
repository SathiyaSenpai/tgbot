import re

with open('modules/notes.py', 'r') as f:
    content = f.read()

# First, remove @group_only from all notes commands
content = re.sub(r'@group_only\n', '', content)

# Remove @admin_required and @owner_required to handle them manually? 
# Or keep them and just bypass them since in PM they return early, then we do our own check.
# Actually, decorators.py says:
# if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
#     return await func(update, context, *args, **kwargs)
# So @admin_required lets PMs pass through!
# We can just manually check permissions inside if it's PM.

RESOLVE_CHAT_CODE = '''
    user = update.effective_user
    chat_id = update.effective_chat.id
    is_pm = update.effective_chat.type == ChatType.PRIVATE
    
    if is_pm:
        db = context.bot_data["db"]
        chat_id = await db.fetchval("SELECT chat_id FROM connections WHERE user_id = ?", (user.id,))
        if not chat_id:
            await update.effective_message.reply_text("Kyaa! You need to connect to a group first, senpai! (/connect)", parse_mode=ParseMode.HTML)
            return
'''

ADMIN_CHECK_CODE = '''
    if is_pm:
        from utils.decorators import is_user_admin
        if not await is_user_admin(chat_id, user.id, context):
            await update.effective_message.reply_text("B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~")
            return
'''

OWNER_CHECK_CODE = '''
    if is_pm:
        from utils.decorators import is_user_owner
        if not await is_user_owner(chat_id, user.id, context):
            await update.effective_message.reply_text("Eeeh?! (・_・;) Only the group owner can tell me to do that!")
            return
'''

def replace_save(match):
    body = match.group(2)
    # remove chat_id = update.effective_chat.id
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + ADMIN_CHECK_CODE + body

def replace_get(match):
    body = match.group(2)
    return match.group(1) + body # get_note just passes name to send_note

def replace_send(match):
    body = match.group(2)
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + body

def replace_list(match):
    body = match.group(2)
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + body

def replace_clear(match):
    body = match.group(2)
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + ADMIN_CHECK_CODE + body

def replace_clearall(match):
    body = match.group(2)
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + OWNER_CHECK_CODE + body

def replace_toggle(match):
    body = match.group(2)
    body = re.sub(r'\s+chat_id = update\.effective_chat\.id', '', body)
    return match.group(1) + RESOLVE_CHAT_CODE + ADMIN_CHECK_CODE + body

content = re.sub(r'(async def save_note.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_save, content, flags=re.DOTALL)
content = re.sub(r'(async def send_note.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_send, content, flags=re.DOTALL)
content = re.sub(r'(async def list_notes.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_list, content, flags=re.DOTALL)
content = re.sub(r'(async def clear_note.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_clear, content, flags=re.DOTALL)
content = re.sub(r'(async def clearall_notes.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_clearall, content, flags=re.DOTALL)
content = re.sub(r'(async def toggle_privatenotes.*?:\s+db = context\.bot_data\["db"\])(.*?)(\n@|\Z)', replace_toggle, content, flags=re.DOTALL)


with open('modules/notes.py', 'w') as f:
    f.write(content)

