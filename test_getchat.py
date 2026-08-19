import asyncio
from telegram import Bot

async def test():
    bot = Bot("7358744040:AAF0_hC9H7Hq8J-5qU9R0z8H0sM1aR6yA8A") # Use a dummy or find a way. Wait, I can't.
    try:
        chat = await bot.get_chat("@NandhiniBot")
        print(chat.id)
    except Exception as e:
        print(e)

# asyncio.run(test())
