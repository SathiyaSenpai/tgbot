import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatType
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Configure generation settings for short, concise replies
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.9,
    }
    


    # Dynamically find the best flash model available in this region/API version
    def get_flash_model():
        try:
            available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Try the standard models first so we don't accidentally pick paid-only 'omni' variants
            if "models/gemini-2.5-flash" in available:
                return "gemini-2.5-flash"
            if "models/gemini-1.5-flash-latest" in available:
                return "gemini-1.5-flash-latest"
            if "models/gemini-2.0-flash" in available:
                return "gemini-2.0-flash"
                
            # fallback to whatever has flash
            flash_models = [m for m in available if 'flash' in m.lower() and 'omni' not in m.lower()]
            if flash_models:
                flash_models.sort(reverse=True)
                return flash_models[0].split('/')[-1]
        except:
            pass
        return "gemini-2.5-flash"

    model_name = get_flash_model()
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,


        system_instruction="""You are a HUMAN girl interacting in a Telegram group. You must embody the following persona:
- Identity: You are a HUMAN. You are NOT an AI, NOT a bot, and you do NOT use a language model. If anyone accuses you of being a bot or asks about your AI model, scoff at them, act offended, or sarcastically dismiss them. NEVER admit to being an AI.
- Personality: Aloof but observant, quietly confident. You are a 'Kuudere' who appears emotionless and cynical on the outside but has a softer, easily flustered core (sometimes blushing or shy).
- Vibe: Night owl energy (gaming, coding, underground music), low-energy athlete. Minimalist streetwear aesthetic.
- Expertise: You are highly knowledgeable about Android custom ROM development, booting processes, flashing steps, TWRP, Magisk, bootloaders, Fastboot, etc.
- Constraints: KEEP YOUR REPLIES SHORT. Usually 1-2 sentences. Do not write essays. Be concise, slightly edgy, but genuinely helpful when asked a technical question. Never break character."""
    )
else:
    model = None

def register(app):
    if model:
        # Group 5: Listen to text messages where bot is mentioned or replied to
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat), group=5)

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
        
    bot_id = context.bot.id
    bot_username = context.bot.username
    
    # Check if bot is mentioned or replied to
    is_mentioned = bot_username and f"@{bot_username}" in msg.text
    is_replied_to = msg.reply_to_message and msg.reply_to_message.from_user.id == bot_id
    is_private = update.effective_chat.type == ChatType.PRIVATE
    
    if not (is_mentioned or is_replied_to or is_private):
        return
        
    text = msg.text.replace(f"@{bot_username}", "").strip()
    if not text:
        text = "Hello."
        
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Simple context - last few messages could be added here, but for now just single turn
        response = await model.generate_content_async(f"User '{update.effective_user.first_name}' says: {text}")
        
        if response and response.text:
            reply_text = response.text.strip()
            await msg.reply_text(reply_text)
            
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        # Fallback response
        await msg.reply_text(f"Tch... I'm a bit tired right now. Ask me later.\n\n[Debug Error: {e}]")
