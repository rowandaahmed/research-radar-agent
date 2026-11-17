import os
from dotenv import load_dotenv

# Load variables from the project root .env file
load_dotenv()

# Read the Gemini API key
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    print("Gemini API key loaded successfully!")
else:
    print("ERROR: Gemini API key not found!")