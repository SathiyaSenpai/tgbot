import logging
import random
import datetime
from telegram.ext import ContextTypes
from modules.ai_chat import model

logger = logging.getLogger(__name__)

def register(app):
    if model:
        # Schedule the random chatter job to run every 2.5 hours (150 minutes)
        app.job_queue.run_repeating(random_chat_job, interval=150 * 60, first=60)

async def random_chat_job(context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data.get("db")
    if not db or not model:
        return
        
    try:
        # Get all active groups (where we have settings or recent activity)
        rows = await db.fetchall("SELECT chat_id FROM chats WHERE chat_type IN ('group', 'supergroup')")
        if not rows:
            return
            
        for row in rows:
            chat_id = row["chat_id"]
            
            # 25% chance to speak every 2.5 hours = roughly 2-3 times a day
            if random.random() > 0.25:
                continue
                
            # Get current time of day to influence the prompt
            hour = datetime.datetime.now().hour
            if 5 <= hour < 12:
                time_context = "morning. Maybe say 'good morning' or complain about waking up early."
            elif 12 <= hour < 17:
                time_context = "afternoon. Maybe mention being bored, or working on some code/custom ROM."
            elif 17 <= hour < 22:
                time_context = "evening. Maybe mention gaming or chilling."
            else:
                time_context = "late night. Emphasize your night owl energy."
                
            day_of_week = datetime.datetime.now().weekday()
            if day_of_week >= 5:
                time_context += " It is the weekend."
                
            prompt = f"Write a single, spontaneous, short message (1-2 sentences) to send to a group chat. The current time context is: {time_context}. Remember your persona: Kuudere, aloof, night owl, custom ROM developer. Do not use quotes around your message, just output the message directly."
            
            try:
                response = model.generate_content(prompt)
                if response and response.text:
                    await context.bot.send_message(chat_id=chat_id, text=response.text.strip())
            except Exception as e:
                logger.error(f"Error generating random chat for {chat_id}: {e}")
                
    except Exception as e:
        logger.error(f"Error in random_chat_job: {e}")
