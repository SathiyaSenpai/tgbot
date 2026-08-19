import re

with open('modules/ai_chat.py', 'r') as f:
    content = f.read()

# Instead of hardcoding "gemini-1.5-flash", let's use a function to find the best flash model.
REPLACEMENT = """
    # Dynamically find the best flash model available in this region/API version
    def get_flash_model():
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower()]
            if models:
                # prefer 2.5 over 1.5
                models.sort(reverse=True)
                return models[0]
        except:
            pass
        return "gemini-2.5-flash"

    model_name = get_flash_model()
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
"""

content = content.replace('''    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,''', REPLACEMENT)

with open('modules/ai_chat.py', 'w') as f:
    f.write(content)

with open('modules/random_chatter.py', 'r') as f:
    content2 = f.read()

content2 = content2.replace('''    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,''', REPLACEMENT)

# Wait, random_chatter.py doesn't instantiate the model, it imports it from ai_chat!
