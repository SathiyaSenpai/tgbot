import os
import glob
import re

ANIME_REPLACEMENTS = {
    '"❌ You need to be an admin to use this command."': '"B-baka! (︶︹︺) You need to be an admin to tell me what to do, senpai~"',
    '"❌ Only the bot owner can use this command."': '"Gomen nasai! (｡>﹏<｡) Only my master can use this command!"',
    '"❌ Only the group owner can use this command."': '"Eeeh?! (・_・;) Only the group owner can tell me to do that!"',
    '"❌ Failed to verify bot permissions."': '"Uwah~ (╥﹏╥) I couldn\'t check my permissions... something went wrong!"',
    '"❌ I need \'Restrict Members\' admin permission in this group to do this."': '"Gomen, senpai~ (╥﹏╥) I need the \'Restrict Members\' permission to do this! Please give it to me~"',
    '"❌ I need \'Delete Messages\' admin permission in this group to do this."': '"Senpai... (｡•́︿•̀｡) I can\'t delete messages without the \'Delete Messages\' permission!"',
    '"❌ I need \'Pin Messages\' admin permission in this group to do this."': '"I can\'t pin anything! (ノ﹏ヽ) I need the \'Pin Messages\' permission, senpai~"',
    '"❌ I need to be an admin in this group to do this."': '"E-eh?! (O_O) I need to be an admin first before I can help you with that!"',
    '"❌ This command only works in private chat."': '"Kyaa! (⁄ ⁄•⁄ω⁄•⁄ ⁄) Let\'s do this in a private chat, okay?"',
    '"❌ This command only works in groups."': '"Senpai~ this command is only for groups! (´• ω •`)"',
    '"Please specify a user to ban."': '"Who do you want me to ban, senpai? (・`ω´・) Please specify someone!"',
    '"You cannot act on this user."': '"I-I can\'t do that to them! (´-﹏-`；) They are too powerful!"',
    'f"Failed to ban: {e}"': 'f"Uwaaah~ (╥﹏╥) I couldn\'t ban them: {e}"',
    '"Reply to a message to dban."': '"Senpai, you have to reply to their message so I know who to delete! (｀･ω･´)"',
    '"Please specify a user."': '"Who is it, senpai? You need to specify a user! (*・ω・)ﾉ"',
    '"Reply to a message."': '"You need to reply to a message, senpai! (´• ω •`)"',
    '"Usage: /dtban <time> [reason]"': '"Usage: /dtban <time> [reason] ~ Don\'t forget the time, senpai! (｡♥‿♥｡)"',
}

files = glob.glob('modules/*.py') + glob.glob('utils/*.py')
for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()
        
    original_content = content
    for old_str, new_str in ANIME_REPLACEMENTS.items():
        content = content.replace(old_str, new_str)
        
    if 'CommandHandler' in content and 'PrefixHandler' not in content:
        content = re.sub(r'(from telegram\.ext import.*?)(CommandHandler)(.*?)', r'\1\2, PrefixHandler\3', content, count=1, flags=re.DOTALL)
        
    # Find all app.add_handler(CommandHandler(...)) and duplicate them with PrefixHandler
    # We will use regex to find app.add_handler(CommandHandler(...)) lines
    
    def replacer(match):
        full_line = match.group(0)
        cmd_args = match.group(1) # e.g. "ban", cb
        if 'filters' in full_line or 'group=' in full_line:
            # We'll just replace CommandHandler with PrefixHandler(['!', '?'],
            prefix_line = full_line.replace('CommandHandler(', "PrefixHandler(['!', '?'], ")
            return f"{full_line}\n    {prefix_line}"
        else:
            prefix_line = full_line.replace('CommandHandler(', "PrefixHandler(['!', '?'], ")
            return f"{full_line}\n    {prefix_line}"

    content = re.sub(r'^[ \t]*app\.add_handler\(\s*CommandHandler\((.*?)\).*', replacer, content, flags=re.MULTILINE)

    if original_content != content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filepath}")

