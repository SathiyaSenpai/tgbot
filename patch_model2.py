with open('modules/ai_chat.py', 'r') as f:
    content = f.read()

REPLACEMENT = """
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
"""

import re
# We need to replace the get_flash_model block
content = re.sub(r'    # Dynamically find the best flash model.*?        generation_config=generation_config,', REPLACEMENT, content, flags=re.DOTALL)

with open('modules/ai_chat.py', 'w') as f:
    f.write(content)
