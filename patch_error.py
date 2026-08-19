with open('modules/ai_chat.py', 'r') as f:
    content = f.read()

content = content.replace(
    'await msg.reply_text("Tch... I\'m a bit tired right now. Ask me later.")',
    'await msg.reply_text(f"Tch... I\'m a bit tired right now. Ask me later.\\n\\n[Debug Error: {e}]")'
)

with open('modules/ai_chat.py', 'w') as f:
    f.write(content)
