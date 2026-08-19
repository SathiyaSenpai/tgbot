import asyncio
import google.generativeai as genai

async def test():
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        # we know it will fail auth, but let's see WHICH exception it raises
        print("Calling sync...")
        res = model.generate_content("hello")
        print(res)
    except Exception as e:
        print(f"Error sync: {e}")

    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        print("Calling async...")
        res = await model.generate_content_async("hello")
        print(res)
    except Exception as e:
        print(f"Error async: {e}")

asyncio.run(test())
