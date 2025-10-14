import os
from dotenv import load_dotenv
from ollama import Client

load_dotenv()

client = Client(
    host="https://ollama.com",
    headers={'Authorization': f'Bearer {os.getenv("OLLAMA_API_KEY")}'}
)

def main():
    print("🚀 GPT-OSS 120B Chatbot (FREE Tier)")
    print("Type 'quit' to exit\n")
    
    messages = []  # Keep conversation history
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            break
            
        # Add to conversation
        messages.append({'role': 'user', 'content': user_input})
        
        print("🤖 GPT-OSS: ", end='', flush=True)
        
        # Get response
        response = client.chat(
            model='gpt-oss:120b',
            messages=messages,
            stream=True
        )
        
        full_response = ""
        for part in response:
            content = part['message']['content']
            print(content, end='', flush=True)
            full_response += content
            
        print("\n" + "-"*60)
        
        # Add AI response to history
        messages.append({'role': 'assistant', 'content': full_response})

if __name__ == "__main__":
    main()