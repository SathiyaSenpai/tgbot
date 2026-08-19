import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import OWNER_ID, COMMIT_POLL_INTERVAL
from utils.decorators import admin_required, owner_required

logger = logging.getLogger(__name__)

ASB_SOURCES = {
    "LineageOS": {
        "23.2": "lineage-23.2",
    },
    "crdroidandroid": {
        "16.0": "16.0",
    },
}


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
    app.add_handler(CommandHandler("addasb", addasb), group=0)
    app.add_handler(CommandHandler("rmasb", rmasb), group=0)

    app.job_queue.run_repeating(check_all_repos, interval=COMMIT_POLL_INTERVAL * 60, first=30)
    app.job_queue.run_repeating(check_asb_job, interval=COMMIT_POLL_INTERVAL * 60, first=60, name="check_asb")


@admin_required
async def addrepo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /addrepo <owner/repo> [branch]")
        return

    repo_str = context.args[0]
    if "/" not in repo_str:
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
        await update.effective_message.reply_text(f"✅ Now tracking <b>{owner}/{repo}</b> on branch <b>{branch}</b>.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error adding repo: {e}")
        await update.effective_message.reply_text("Failed to add repository to tracking list.")


@admin_required
async def rmrepo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /rmrepo <owner/repo>")
        return

    repo_str = context.args[0]
    if "/" not in repo_str:
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
            await update.effective_message.reply_text(f"🗑️ Removed <b>{owner}/{repo}</b> from tracking.", parse_mode=ParseMode.HTML)
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

        text = "📦 <b>Tracked Repositories:</b>\n\n"
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

    if "/" not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return

    owner, repo = repo_str.split("/", 1)
    db = context.bot_data["db"]

    try:
        row = await db.fetchone("SELECT id FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))
        if row:
            await db.execute("UPDATE tracked_repos SET branch = ? WHERE id = ?", (branch, row[0]))
            await db.execute("DELETE FROM repo_cache WHERE repo_id = ?", (row[0],))
            await db.commit()
            await update.effective_message.reply_text(f"✅ Branch for <b>{owner}/{repo}</b> set to <b>{branch}</b>.", parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text("Repository not found in tracking list.")
    except Exception as e:
        logger.error(f"Error setting branch: {e}")
        await update.effective_message.reply_text("Failed to update branch.")


async def commits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Usage: /commits <owner/repo> [branch]")
        return

    repo_str = context.args[0]
    if "/" not in repo_str:
        await update.effective_message.reply_text("Invalid format. Use <owner/repo>")
        return

    owner, repo = repo_str.split("/", 1)
    branch = context.args[1] if len(context.args) > 1 else None
    db = context.bot_data["db"]
    github = context.bot_data.get("github")

    if not github:
        await update.effective_message.reply_text("GitHub client not configured.")
        return

    try:
        if not branch:
            row = await db.fetchone("SELECT branch FROM tracked_repos WHERE owner = ? AND repo = ?", (owner, repo))
            branch = row[0] if row else "main"

        data = await github.get_commits(owner, repo, branch)
        status = data.get("status", 0)
        commits_list = data.get("commits", [])

        if status == 404:
            await update.effective_message.reply_text(f"Repository or branch not found (tried branch: {branch}).")
            return

        if not commits_list or status == 304:
            await update.effective_message.reply_text("No recent commits found.")
            return

        text = f"🔄 <b>Latest commits for {owner}/{repo} @ {branch}:</b>\n\n"
        for commit in commits_list[:5]:
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
        await update.effective_message.reply_text("✅ You are now subscribed to all commit notifications.")
    except Exception as e:
        logger.error(f"Error subscribing user {user_id}: {e}")
        await update.effective_message.reply_text("Failed to subscribe.")


async def untrackme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    user_id = update.effective_user.id
    try:
        await db.execute("DELETE FROM commit_subscribers WHERE user_id = ? AND repo_id = 0", (user_id,))
        await db.commit()
        await update.effective_message.reply_text("🚫 You have been unsubscribed from commit notifications.")
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

        text = "👥 <b>Commit Subscribers:</b>\n"
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

        for name in ["check_all_repos", "check_asb"]:
            jobs = context.job_queue.get_jobs_by_name(name)
            for job in jobs:
                job.schedule_removal()

        context.job_queue.run_repeating(check_all_repos, interval=minutes * 60, first=0, name="check_all_repos")
        context.job_queue.run_repeating(check_asb_job, interval=minutes * 60, first=0, name="check_asb")

        await update.effective_message.reply_text(f"✅ Polling interval set to {minutes} minutes.", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.effective_message.reply_text("Please provide a valid positive integer for minutes.")
    except Exception as e:
        logger.error(f"Error setting poll interval: {e}")


@owner_required
async def addasb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a ROM org + branch to ASB tracking. Usage: /addasb <org> <branch>"""
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /addasb <org> <branch>\nExample: /addasb LineageOS lineage-23.2")
        return

    org, branch = context.args[0], context.args[1]
    db = context.bot_data["db"]

    try:
        await db.execute(
            "INSERT OR IGNORE INTO asb_sources (org, branch) VALUES (?, ?)",
            (org, branch)
        )
        await db.commit()
        await update.effective_message.reply_text(f"✅ Now tracking ASB for <b>{org}</b> on branch <b>{branch}</b>.", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error adding ASB source: {e}")
        await update.effective_message.reply_text("Failed to add ASB source.")


@owner_required
async def rmasb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a ROM org + branch from ASB tracking."""
    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /rmasb <org> <branch>")
        return

    org, branch = context.args[0], context.args[1]
    db = context.bot_data["db"]

    try:
        await db.execute("DELETE FROM asb_sources WHERE org = ? AND branch = ?", (org, branch))
        await db.commit()
        await update.effective_message.reply_text(f"🗑️ Removed ASB tracking for <b>{org}</b> ({branch}).", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error removing ASB source: {e}")
        await update.effective_message.reply_text("Failed to remove ASB source.")


async def checkasb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch current security patch levels from all tracked ROM orgs."""
    msg = await update.effective_message.reply_text("Fetching security patch levels...")
    db = context.bot_data.get("db")
    github = context.bot_data.get("github")

    if not db or not github:
        await msg.edit_text("GitHub client not initialized.")
        return

    try:
        sources = await db.fetchall("SELECT org, branch FROM asb_sources ORDER BY org, branch")
        if not sources:
            # Fallback to built-in defaults
            sources = []
            for org, branches in ASB_SOURCES.items():
                for label, branch in branches.items():
                    sources.append((org, branch))

        if not sources:
            await msg.edit_text("No ASB sources configured. Use /addasb <org> <branch> to add one.")
            return

        results = []
        for org, branch in sources:
            patch_date = await github.check_asb(org, branch)
            if patch_date:
                results.append(f"<b>{org}</b> ({branch}): <code>{patch_date}</code>")
            else:
                results.append(f"<b>{org}</b> ({branch}): <i>not found</i>")

        final_text = "🔒 <b>Android Security Patch Levels:</b>\n\n" + "\n".join(results)
        await msg.edit_text(final_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error checking ASB: {e}")
        await msg.edit_text("Failed to check security patch levels.")


async def check_asb_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job: check for new security patches and DM the owner."""
    db = context.bot_data.get("db")
    github = context.bot_data.get("github")

    if not db or not github:
        return

    try:
        sources = await db.fetchall("SELECT org, branch FROM asb_sources ORDER BY org, branch")
        if not sources:
            for org, branches in ASB_SOURCES.items():
                for label, branch in branches.items():
                    sources.append((org, branch))

        for org, branch in sources:
            patch_date = await github.check_asb(org, branch)
            if not patch_date:
                continue

            cache_key = f"asb_{org}_{branch}"
            cached = await db.fetchval(
                "SELECT value FROM bot_kv WHERE key = ?", (cache_key,)
            )

            if cached == patch_date:
                continue

            await db.execute(
                "INSERT INTO bot_kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (cache_key, patch_date, patch_date)
            )
            await db.commit()

            if cached is not None:
                msg = (
                    f"🔒 <b>New Security Patch Detected!</b>\n\n"
                    f"<b>{org}</b> ({branch})\n"
                    f"Previous: <code>{cached}</code>\n"
                    f"New: <code>{patch_date}</code>"
                )
                try:
                    await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
                except TelegramError as e:
                    logger.error(f"Failed to DM owner about ASB update: {e}")

    except Exception as e:
        logger.error(f"Error in ASB check job: {e}")


async def check_all_repos(context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    github = context.bot_data.get("github")

    if not db or not github:
        logger.error("Database or GitHub client not found in bot_data.")
        return

    try:
        repos = await db.fetchall("SELECT id, owner, repo, branch FROM tracked_repos")
        for repo_id, owner, repo, branch in repos:
            cache = await db.fetchone("SELECT etag, last_sha FROM repo_cache WHERE repo_id = ?", (repo_id,))
            cached_etag = cache[0] if cache else None
            last_sha = cache[1] if cache else None

            data = await github.get_commits(owner, repo, branch, etag=cached_etag)
            status = data.get("status", 0)
            commits_list = data.get("commits", [])

            if not commits_list or status == 304:
                continue

            new_commits = []
            for commit in commits_list:
                if commit.get("sha") == last_sha:
                    break
                new_commits.append(commit)

            if not new_commits:
                continue

            subscribers = await db.fetchall("SELECT user_id FROM commit_subscribers WHERE repo_id = 0 OR repo_id = ?", (repo_id,))
            new_commits.reverse()

            for commit in new_commits:
                msg = (
                    f"🔔 New commit in <b>{owner}/{repo}</b> @ {branch}\n\n"
                    f"{github.format_commit(commit)}"
                )

                for sub in subscribers:
                    user_id = sub[0]
                    try:
                        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    except TelegramError as e:
                        logger.error(f"Failed to send commit notification to {user_id}: {e}")

            new_last_sha = new_commits[-1].get("sha") if new_commits else last_sha
            new_etag = data.get("etag", cached_etag)

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
