"""
Senpai's Bot - Module Registration
Central handler registration for all modules.
"""
import logging
from telegram.ext import Application

from config import ENABLE_COMMIT_TRACKER, ENABLE_GROUP_MANAGEMENT

logger = logging.getLogger(__name__)


def register_all_handlers(app: Application) -> None:
    from modules.start import register as reg_start
    reg_start(app)
    logger.info("Loaded: start")

    if ENABLE_GROUP_MANAGEMENT:
        try:
            from modules.commandcontrol import register as reg_cmdctrl
            reg_cmdctrl(app)
            logger.info("Loaded: commandcontrol")
        except Exception as e:
            logger.error(f"Failed to load commandcontrol: {e}")

        try:
            from modules.antiflood import register as reg_antiflood
            reg_antiflood(app)
            logger.info("Loaded: antiflood")
        except Exception as e:
            logger.error(f"Failed to load antiflood: {e}")

        modules_group0 = [
            ("admin", "modules.admin"),
            ("mutes", "modules.mutes"),
            ("warnings", "modules.warnings"),
            ("blocklist", "modules.blocklist"),
            ("filters", "modules.filters"),
            ("notes", "modules.notes"),
            ("rules", "modules.rules"),
            ("greetings", "modules.greetings"),
            ("pins", "modules.pins"),
            ("purge", "modules.purge"),
            ("connection", "modules.connection"),
            ("locks", "modules.locks"),
            ("reports", "modules.reports"),
            ("approvals", "modules.approvals"),
            ("logchannel", "modules.logchannel"),
            ("captcha", "modules.captcha"),
            ("scheduled", "modules.scheduled"),
            ("autodelete", "modules.autodelete"),
            ("botsettings", "modules.botsettings"),
            ("misc", "modules.misc"),
        ]

        for name, module_path in modules_group0:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                mod.register(app)
                logger.info(f"Loaded: {name}")
            except Exception as e:
                logger.error(f"Failed to load {name}: {e}")

    if ENABLE_COMMIT_TRACKER:
        try:
            from modules.commits import register as reg_commits
            reg_commits(app)
            logger.info("Loaded: commits")
        except Exception as e:
            logger.error(f"Failed to load commits: {e}")

    logger.info("All modules registered.")
