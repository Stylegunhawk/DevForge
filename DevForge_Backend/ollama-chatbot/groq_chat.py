import os
from dotenv import load_dotenv
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client with API key
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def chat_with_groq(messages, model="llama-3.3-70b-versatile"):
    """Generate a streaming response from Groq."""
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=True,
        stop=None
    )
    
    full_response = ""
    print("🤖 Groq: ", end='', flush=True)
    
    for chunk in completion:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end='', flush=True)
            full_response += content
    
    print("\n" + "="*50)
    return full_response

def main():
    """Interactive chat loop."""
    print("Interactive Groq Chat (type 'exit' or Ctrl+C to quit)")
    print("-" * 50)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    
    try:
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye!")
                break
            if not user_input:
                continue
            
            messages.append({"role": "user", "content": user_input})
            assistant_response = chat_with_groq(messages)
            messages.append({"role": "assistant", "content": assistant_response})
            
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    except Exception as e:
        print(f"\nError: {e}")
        print("Ensure GROQ_API_KEY is set in your .env file and the model is valid.")

if __name__ == "__main__":
    main()