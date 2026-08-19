import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError, BadRequest, Forbidden

from config import OWNER_ID, COMMIT_POLL_INTERVAL
from utils.decorators import admin_required, owner_required

logger = logging.getLogger(__name__)

def register(app):
    app.add_handler(CommandHandler("addrepo", addrepo), group=0)
    app.add_handler(CommandHandler("rmrepo", rmrepo), group=0)
    app.add_handler(CommandHandler("repos", repos), group=0)
    app.add_handler(CommandHandler("setbranch", setbranch), group=0)
    app.add_handler(CommandHandler("commits", commits), group=0)
    app.add_handler(CommandHandler("trackme", trackme), group=0)
    app.add_handler(CommandHandler("untrackme", untrackme), group=0)
    app.add_handler(CommandHandler("trackers", trackers), group=0)
    app.add_handler(CommandHandler("pollinterval", pollinterval), group=0)
    app.add_handler(CommandHandler("checkasb", checkasb), group=0)
    
    app.job_queue.run_repeating(check_all_repos, interval=COMMIT_POLL_INTERVAL * 60, first=30)

@admin_required
async def addrepo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /addrepo <owner/repo> [branch]")
        return
        
    repo_str = context.args[0]
    if "/"not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return
        
    owner, repo = repo_str.split("/", 1)
    branch = context.args[1] if len(context.args) > 1 else "main"
    
    db = context.bot_data["db"]
    try:
        await db.execute(
            "INSERT INTO tracked_repos (owner, repo, branch, added_by, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (owner, repo, branch, update.effective_user.id)
        )
        await db.commit()
        await update.effective_message.reply_text(f"Now tracking <b>{owner}/{repo}</b> on branch <b>{branch}</b>.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error adding repo: {e}")
        await update.effective_message.reply_text("Failed to add repository to tracking list.")

@admin_required
async def rmrepo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /rmrepo <owner/repo>")
        return
        
    repo_str = context.args[0]
    if "/"not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return
        
    owner, repo = repo_str.split("/", 1)
    db = context.bot_data["db"]
    
    try:
        row = await db.fetchone("SELECT id FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))
        if row:
            repo_id = row[0]
            await db.execute("DELETE FROM repo_cache WHERE repo_id = ?", (repo_id,))
            await db.execute("DELETE FROM commit_subscribers WHERE repo_id = ?", (repo_id,))
            await db.execute("DELETE FROM tracked_repos WHERE id = ?", (repo_id,))
            await db.commit()
            await update.effective_message.reply_text(f"️ Removed <b>{owner}/{repo}</b> from tracking.", parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text("Repository not found in tracking list.")
    except Exception as e:
        logger.error(f"Error removing repo: {e}")
        await update.effective_message.reply_text("Failed to remove repository.")

async def repos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    try:
        rows = await db.fetchall("SELECT owner, repo, branch FROM tracked_repos ORDER BY owner, repo")
        if not rows:
            await update.effective_message.reply_text("No repositories are currently being tracked.")
            return
            
        text = "<b>Tracked Repositories:</b>\n\n"
        for owner, repo, branch in rows:
            text += f"• <code>{owner}/{repo}</code> (<i>{branch}</i>)\n"
            
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error listing repos: {e}")
        await update.effective_message.reply_text("Failed to fetch repository list.")

@admin_required
async def setbranch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /setbranch <owner/repo> <branch>")
        return
        
    repo_str = context.args[0]
    branch = context.args[1]
    
    if "/"not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return
        
    owner, repo = repo_str.split("/", 1)
    db = context.bot_data["db"]
    
    try:
        row = await db.fetchone("SELECT id FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))
        if row:
            await db.execute("UPDATE tracked_repos SET branch = ? WHERE id = ?", (branch, row[0]))
            await db.execute("DELETE FROM repo_cache WHERE repo_id = ?", (row[0],)) # Clear cache to fetch new branch
            await db.commit()
            await update.effective_message.reply_text(f"Branch for <b>{owner}/{repo}</b> set to <b>{branch}</b>.", parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text("Repository not found in tracking list.")
    except Exception as e:
        logger.error(f"Error setting branch: {e}")
        await update.effective_message.reply_text("Failed to update branch.")

async def commits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /commits <owner/repo>")
        return
        
    repo_str = context.args[0]
    if "/"not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return
        
    owner, repo = repo_str.split("/", 1)
    db = context.bot_data["db"]
    github = context.bot_data.get("github")
    
    if not github:
        await update.effective_message.reply_text("GitHub client not configured.")
        return
        
    try:
        row = await db.fetchone("SELECT branch FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))
        branch = row[0] if row else "main"
        
        commits_data = await github.get_commits(owner, repo, branch)
        if not commits_data or getattr(commits_data, 'status', 200) == 304:
            await update.effective_message.reply_text("Could not fetch commits or no recent commits found.")
            return
            
        text = f"<b>Latest commits for {owner}/{repo} @ {branch}:</b>\n\n"
        for commit in commits_data[:5]: # show last 5
            text += github.format_commit(commit) + "\n"
            
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        await update.effective_message.reply_text("Failed to fetch commits.")

async def trackme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    try:
        await db.execute(
            "INSERT OR IGNORE INTO commit_subscribers (user_id, repo_id) VALUES (?, 0)",
            (user_id,)
        )
        await db.commit()
        await update.effective_message.reply_text("You are now subscribed to all commit notifications.")
    except Exception as e:
        logger.error(f"Error subscribing user {user_id}: {e}")
        await update.effective_message.reply_text("Failed to subscribe.")

async def untrackme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    try:
        await db.execute("DELETE FROM commit_subscribers WHERE user_id = ? AND repo_id = 0", (user_id,))
        await db.commit()
        await update.effective_message.reply_text("You have been unsubscribed from commit notifications.")
    except Exception as e:
        logger.error(f"Error unsubscribing user {user_id}: {e}")
        await update.effective_message.reply_text("Failed to unsubscribe.")

@admin_required
async def trackers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    try:
        rows = await db.fetchall("SELECT DISTINCT user_id FROM commit_subscribers")
        if not rows:
            await update.effective_message.reply_text("No one is currently subscribed to commit notifications.")
            return
            
        text = "<b>Commit Subscribers:</b>\n"
        for row in rows:
            text += f"• <code>{row[0]}</code>\n"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error listing trackers: {e}")
        await update.effective_message.reply_text("Failed to list trackers.")

@owner_required
async def pollinterval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(f"Usage: /pollinterval <minutes>\nCurrent interval: {COMMIT_POLL_INTERVAL} minutes")
        return
        
    try:
        minutes = int(context.args[0])
        if minutes < 1:
            raise ValueError()
            
        jobs = context.job_queue.get_jobs_by_name("check_all_repos")
        if jobs:
            for job in jobs:
                job.schedule_removal()
        context.job_queue.run_repeating(check_all_repos, interval=minutes * 60, first=0, name="check_all_repos")
        
        await update.effective_message.reply_text(f"Polling interval set to {minutes} minutes. Note: This will reset on bot restart unless saved to config.", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.effective_message.reply_text("Please provide a valid positive integer for minutes.")
    except Exception as e:
        logger.error(f"Error setting poll interval: {e}")

@admin_required
async def checkasb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Initiating manual ASB check...")
    context.job_queue.run_once(check_all_repos, 0)

async def check_all_repos(context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    github = context.bot_data.get("github")
    
    if not db or not github:
        logger.error("Database or GitHub client not found in bot_data.")
        return
        
    try:
        repos = await db.fetchall("SELECT id, owner, repo, branch FROM tracked_repos")
        for repo_id, owner, repo, branch in repos:
            cache = await db.fetchone("SELECT etag, last_sha, last_security_patch FROM repo_cache WHERE repo_id = ?", (repo_id,))
            cached_etag = cache[0] if cache else None
            last_sha = cache[1] if cache else None
            last_security_patch = cache[2] if cache else None
            
            commits_data = await github.get_commits(owner, repo, branch, etag=cached_etag)
            
            if not commits_data or getattr(commits_data, 'status', 200) == 304:
                continue
                
            new_commits = []
            for commit in commits_data:
                if commit.get("sha") == last_sha:
                    break
                new_commits.append(commit)
                
            if not new_commits:
                continue
                
            subscribers = await db.fetchall("SELECT user_id FROM commit_subscribers WHERE repo_id = 0 OR repo_id = ?", (repo_id,))
            new_commits.reverse() # Chronological
            
            for commit in new_commits:
                msg = (
                    f"New commit in <b>{owner}/{repo}</b> @ {branch}\n\n"
                    f"{github.format_commit(commit)}"
                )
                
                files_touched = commit.get("files", [])
                asb_updated = False
                new_patch_date = "Unknown"
                for f in files_touched:
                    if f.get("filename") == "core/version_defaults.mk":
                        asb_updated = True
                        break
                        
                for sub in subscribers:
                    user_id = sub[0]
                    try:
                        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                        if asb_updated and "android_build"in repo.lower():
                            asb_msg = (
                                f"<b>SECURITY PATCH UPDATE</b>\n"
                                f"{owner}/{repo} @ {branch}\n"
                                f"{last_security_patch or 'Unknown'} → {new_patch_date}"
                            )
                            await context.bot.send_message(chat_id=user_id, text=asb_msg, parse_mode=ParseMode.HTML)
                    except TelegramError as e:
                        logger.error(f"Failed to send commit notification to {user_id}: {e}")
            
            new_last_sha = new_commits[-1].get("sha") if new_commits else last_sha
            new_etag = getattr(commits_data, 'headers', {}).get('ETag', cached_etag)
            
            if cache:
                await db.execute(
                    "UPDATE repo_cache SET last_sha = ?, etag = ?, last_checked = CURRENT_TIMESTAMP WHERE repo_id = ?",
                    (new_last_sha, new_etag, repo_id)
                )
            else:
                await db.execute(
                    "INSERT INTO repo_cache (repo_id, last_sha, etag, last_checked) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (repo_id, new_last_sha, new_etag)
                )
            await db.commit()
            
    except Exception as e:
        logger.error(f"Error in check_all_repos job: {e}")
