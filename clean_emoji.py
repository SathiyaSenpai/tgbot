import os
import re

# Regex to match emojis and common symbols (but exclude typical punctuation like dashes, bullets)
# \u2600-\u26FF: Misc symbols (sun, moon, weather, etc.)
# \u2700-\u27BF: Dingbats (checkmarks, crosses, etc.)
# \U0001F300-\U0001F5FF: Misc Symbols and Pictographs
# \U0001F600-\U0001F64F: Emoticons
# \U0001F680-\U0001F6FF: Transport and Map
# \U0001F900-\U0001F9FF: Supplemental Symbols and Pictographs
emoji_pattern = re.compile(r'[\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF]+')

def remove_emoji(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    clean_text = emoji_pattern.sub('', text)
    
    # Fix the leading space issue after quote if an emoji was stripped at the start
    clean_text = clean_text.replace('"', '"').replace("'", "'")
    
    if text != clean_text:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(clean_text)
            print(f"Cleaned {filepath}")

for root, dirs, files in os.walk('.'):
    if '.venv'in root or '.git'in root or 'data'in root:
        continue
    for file in files:
        if file.endswith('.py'):
            remove_emoji(os.path.join(root, file))

