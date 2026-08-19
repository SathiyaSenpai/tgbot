with open('modules/commits.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('async def commits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    if not context.args:\n        await update.effective_message.reply_text("Usage: /commits <owner/repo>")', 'async def commits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    if not context.args:\n        await update.effective_message.reply_text("Usage: /commits <owner/repo> [branch]")')

text = text.replace('    owner, repo = repo_str.split("/", 1)\n    db = context.bot_data["db"]', '    owner, repo = repo_str.split("/", 1)\n    branch = context.args[1] if len(context.args) > 1 else None\n    db = context.bot_data["db"]')

text = text.replace('row = await db.fetchone("SELECT branch FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))\n        branch = row[0] if row else "main"', 'if not branch:\n            row = await db.fetchone("SELECT branch FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))\n            branch = row[0] if row else "main"')

text = text.replace("commits_data = await github.get_commits(owner, repo, branch)\n        if not commits_data or getattr(commits_data, 'status', 200) == 304:\n            await update.effective_message.reply_text(\"Could not fetch commits or no recent commits found.\")\n            return\n            \n        text = f\"🔄 <b>Latest commits for {owner}/{repo} @ {branch}:</b>\\n\\n\"\n        for commit in commits_data[:5]: # show last 5", "data = await github.get_commits(owner, repo, branch)\n        status = data.get('status', 0)\n        commits_list = data.get('commits', [])\n        \n        if status == 404:\n            await update.effective_message.reply_text(f'Repository or branch not found (tried branch: {branch}).')\n            return\n            \n        if not commits_list or status == 304:\n            await update.effective_message.reply_text(\"Could not fetch commits or no recent commits found.\")\n            return\n            \n        text = f\"🔄 <b>Latest commits for {owner}/{repo} @ {branch}:</b>\\n\\n\"\n        for commit in commits_list[:5]: # show last 5")

text = text.replace("commits_data = await github.get_commits(owner, repo, branch, etag=cached_etag)\n            \n            if not commits_data or getattr(commits_data, 'status', 200) == 304:\n                continue\n                \n            new_commits = []\n            for commit in commits_data:", "data = await github.get_commits(owner, repo, branch, etag=cached_etag)\n            status = data.get('status', 0)\n            commits_list = data.get('commits', [])\n            \n            if not commits_list or status == 304:\n                continue\n                \n            new_commits = []\n            for commit in commits_list:")

text = text.replace("new_etag = getattr(commits_data, 'headers', {}).get('ETag', cached_etag)", "new_etag = data.get('etag', cached_etag)")

with open('modules/commits.py', 'w', encoding='utf-8') as f:
    f.write(text)
