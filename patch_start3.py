import re

with open('modules/start.py', 'r') as f:
    content = f.read()

NEW_HELP = r'''HELP_CATEGORIES = {
    "ai": {
        "title": "AI & Chat",
        "commands": (
            "I don't need commands to talk to you. Just tag me or reply to my messages and I'll respond.\\n\\n"
            "I also occasionally drop a message in the group when I feel like it."
        ),
    },
    "misc": {
        "title": "Misc & Tools",
        "commands": (
            "/tr - Translate text\\n"
            "/tts - Text to speech\\n"
            "/id - Get IDs\\n"
            "/info - User info\\n"
            "/ping - Check if alive"
        ),
    },
    "github": {
        "title": "Commit Tracker",
        "commands": (
            "/addrepo - Track repo\\n"
            "/rmrepo - Untrack repo\\n"
            "/repos - List tracked\\n"
            "/setbranch - Change branch\\n"
            "/commits - Fetch commits\\n"
            "/trackme - Subscribe to PMs\\n"
            "/untrackme - Unsubscribe"
        ),
    },
    "schedule": {
        "title": "Scheduling",
        "commands": (
            "/schedule - Schedule message\\n"
            "/schedules - List pending\\n"
            "/cancelschedule - Cancel"
        ),
    },
    "settings": {
        "title": "Settings",
        "commands": (
            "/setlog - Set log channel\\n"
            "/setbotname - Change name\\n"
            "/setbotphoto - Change photo"
        ),
    }
}'''

content = re.sub(r'HELP_CATEGORIES = \{.*?^\}', NEW_HELP, content, flags=re.DOTALL | re.MULTILINE)

with open('modules/start.py', 'w') as f:
    f.write(content)
