import re

with open('utils/helpers.py', 'r') as f:
    content = f.read()

# Replace get_target_user entirely
new_get_target = '''async def get_target_user(
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
        # Username resolution needs cache, for now return None to prompt failure
        return None, rest

    if return_rest:
        return None, " ".join(args)

    return None, None'''

import re
# Regex to replace from 'async def get_target_user' to the next function 'async def is_user_in_chat'
content = re.sub(r'async def get_target_user.*?return None, " "\.join\(args\), None', new_get_target, content, flags=re.DOTALL)

with open('utils/helpers.py', 'w') as f:
    f.write(content)

