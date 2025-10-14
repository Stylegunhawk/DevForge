import requests
import json

url = "http://localhost:4001/api/generate"

def chat_with_gemma(message):
    """Stream response from local Ollama model"""
    data = {
        "model": "gemma3:1b",  # Replace with your model
        "prompt": message,
        "max_tokens": 200
    }

    # Use stream=True to get incremental updates
    with requests.post(url, json=data, stream=True) as response:
        print("🤖 Gemma3: ", end='', flush=True)
        
        # Each line is a JSON fragment
        for line in response.iter_lines(decode_unicode=True):
            if line:
                obj = json.loads(line)
                print(obj.get("response", ""), end='', flush=True)
        print("\n" + "="*50)

# Test it
if __name__ == "__main__":
    chat_with_gemma("Explain AI in simple terms.")
