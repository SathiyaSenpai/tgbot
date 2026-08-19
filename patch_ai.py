import re

with open('modules/ai_chat.py', 'r') as f:
    content = f.read()

content = content.replace("model.generate_content(", "await model.generate_content_async(")

with open('modules/ai_chat.py', 'w') as f:
    f.write(content)

with open('modules/random_chatter.py', 'r') as f:
    content2 = f.read()

content2 = content2.replace("model.generate_content(", "await model.generate_content_async(")

with open('modules/random_chatter.py', 'w') as f:
    f.write(content2)
