import google.generativeai as genai

# We won't provide an API key, we just want to see if the GenerativeModel init throws an error
try:
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.9,
        "max_output_tokens": 150,
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction="Test instruction"
    )
    print("Init successful!")
except Exception as e:
    print(f"Error: {e}")
