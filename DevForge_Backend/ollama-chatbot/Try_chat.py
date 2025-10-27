import requests
import json

url = "http://localhost:4001/api/generate"

def main():
    print("🚀 Gemma3 Chatbot (Local)")
    print("Type 'quit' to exit\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            break

        # Prepare request data
        data = {
            "model": "gemma3:1b",  # Local model
            "prompt": user_input,
            "max_tokens": 200
        }

        print("🤖 Gemma3: ", end='', flush=True)

        # Stream response
        with requests.post(url, json=data, stream=True) as response:
            full_response = ""
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        obj = json.loads(line)
                        text = obj.get("response", "")
                        print(text, end='', flush=True)
                        full_response += text
                    except json.JSONDecodeError:
                        continue

        print("\n" + "-"*60)

if __name__ == "__main__":
    main()
