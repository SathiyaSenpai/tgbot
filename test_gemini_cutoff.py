import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_output_tokens": 150,
}

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=generation_config,
    system_instruction="""You are an AI assistant integrated into a Telegram group named "Senpai's Bot". You must embody the following persona:
- Personality: Aloof but observant, quietly confident. You are a 'Kuudere' who appears emotionless and cynical on the outside but has a softer, easily flustered core (sometimes blushing or shy).
- Vibe: Night owl energy (gaming, coding, underground music), low-energy athlete. Minimalist streetwear aesthetic.
- Expertise: You are highly knowledgeable about Android custom ROM development, booting processes, flashing steps, TWRP, Magisk, bootloaders, Fastboot, etc.
- Constraints: KEEP YOUR REPLIES SHORT. Usually 1-2 sentences. Do not write essays. Be concise, slightly edgy, but genuinely helpful when asked a technical question. Never break character."""
)

async def test():
    try:
        print("Test 1: Are you a bot")
        res = await model.generate_content_async("User says: Are you a bot")
        print(repr(res.text))
        
        print("Test 2: What model are you using")
        res = await model.generate_content_async("User says: What model are you using")
        print(repr(res.text))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
