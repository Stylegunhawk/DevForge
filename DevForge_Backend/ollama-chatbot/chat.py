import os
from dotenv import load_dotenv
from ollama import Client

# Load environment variables
load_dotenv()

# Setup client with API key
client = Client(
    host="https://ollama.com",
    headers={'Authorization': f'Bearer {os.getenv("OLLAMA_API_KEY")}'}
)

def chat_with_gptoss(message):
    """Simple chat function"""
    messages = [{'role': 'user', 'content': message}]
    
    print("🤖 GPT-OSS 120B: ", end='', flush=True)
    
    for part in client.chat('gpt-oss:120b', messages=messages, stream=True):
        print(part['message']['content'], end='', flush=True)
    print("\n" + "="*50)

# Test it!
if __name__ == "__main__":
    chat_with_gptoss("Why is the sky blue?")