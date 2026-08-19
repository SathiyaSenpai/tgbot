import re

with open('utils/helpers.py', 'r') as f:
    content = f.read()

NEW_GET_TARGET = '''async def get_target_user(
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
        username = first_arg.lstrip("@").lower()
        db = context.bot_data.get("db")
        if db:
            row = await db.fetchone("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,))
            if row:
                return row["user_id"], rest
        return None, rest

    if return_rest:
        return None, " ".join(args)

    return None, None'''

content = re.sub(r'async def get_target_user.*?return None, None', NEW_GET_TARGET, content, flags=re.DOTALL)

with open('utils/helpers.py', 'w') as f:
    f.write(content)
