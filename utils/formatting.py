"""
Senpai's Bot - Message Formatting & Fillings Engine
Replaces {placeholder} tags in welcome messages, notes, filters, etc.
"""
import re
from typing import Optional
from telegram import User, Chat, InlineKeyboardButton, InlineKeyboardMarkup


# Pattern to find button syntax: [text](buttonurl://url) and [text](buttonurl://url:same)
BUTTON_REGEX = re.compile(r"\[(.+?)\]\(buttonurl://(.+?)\)")
FILLING_REGEX = re.compile(r"\{(\w+)\}")


def apply_fillings(
    text: str,
    user: Optional[User] = None,
    chat: Optional[Chat] = None,
    member_count: Optional[int] = None,
) -> str:
    if not text:
        return text

    replacements = {}

    if user:
        first = user.first_name or ""
        last = user.last_name or ""
        fullname = f"{first} {last}".strip()
        username = f"@{user.username}" if user.username else first
        mention = f'<a href="tg://user?id={user.id}">{_escape_html(first)}</a>'

        replacements.update({
            "first": _escape_html(first),
            "last": _escape_html(last),
            "fullname": _escape_html(fullname),
            "username": _escape_html(username),
            "mention": mention,
            "id": str(user.id),
        })

    if chat:
        replacements["chatname"] = _escape_html(chat.title or "this chat")

    if member_count is not None:
        replacements["count"] = str(member_count)

    def replace_filling(match):
        key = match.group(1).lower()
        return replacements.get(key, match.group(0))

    return FILLING_REGEX.sub(replace_filling, text)


def extract_buttons(text: str) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    buttons = []
    current_row = []

    for match in BUTTON_REGEX.finditer(text):
        btn_text = match.group(1)
        btn_url = match.group(2)

        same_line = btn_url.endswith(":same")
        if same_line:
            btn_url = btn_url[:-5]  # Remove ":same"

        button = InlineKeyboardButton(text=btn_text, url=btn_url)

        if same_line and current_row:
            current_row.append(button)
        else:
            if current_row:
                buttons.append(current_row)
            current_row = [button]

    if current_row:
        buttons.append(current_row)

    cleaned_text = BUTTON_REGEX.sub("", text).strip()

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
    return cleaned_text, keyboard


def format_welcome(
    text: str,
    user: User,
    chat: Chat,
    bot_username: str,
    member_count: Optional[int] = None,
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    formatted = apply_fillings(text, user=user, chat=chat, member_count=member_count)

    if "{rules}" in formatted:
        rules_url = f"https://t.me/{bot_username}?start=rules_{chat.id}"
        formatted = formatted.replace("{rules}", "")
        # We'll add a rules button
        formatted_clean, keyboard = extract_buttons(formatted)
        rules_btn = InlineKeyboardButton("📜 Rules", url=rules_url)
        if keyboard:
            keyboard.inline_keyboard.append([rules_btn])
        else:
            keyboard = InlineKeyboardMarkup([[rules_btn]])
        return formatted_clean, keyboard

    return extract_buttons(formatted)


def _escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
