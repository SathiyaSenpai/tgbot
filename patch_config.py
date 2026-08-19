with open('config.py', 'r') as f:
    content = f.read()
    
# Add GEMINI_API_KEY
if 'GEMINI_API_KEY' not in content:
    content = content.replace('GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")', 
                              'GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")\nGEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")')
    content = content.replace('if not BOT_TOKEN:', 
                              'if not GEMINI_API_KEY:\n        errors.append("GEMINI_API_KEY is not set. Get it from Google AI Studio.")\n    if not BOT_TOKEN:')
    
    with open('config.py', 'w') as f:
        f.write(content)
