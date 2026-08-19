import asyncio
from telegram import Update, Message, User, Chat, MessageEntity
from telegram.ext import ContextTypes

# We can't easily mock the whole PTB update without overhead.
