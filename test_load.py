import asyncio
from telegram.ext import ApplicationBuilder
from modules import register_all_handlers
import logging
logging.basicConfig(level=logging.INFO)
app = ApplicationBuilder().token("1234:ABCD").build()
register_all_handlers(app)
