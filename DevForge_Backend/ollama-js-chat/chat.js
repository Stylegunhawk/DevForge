require('dotenv').config();
const { Ollama } = require('ollama');

const ollama = new Ollama({
    host: "https://ollama.com",
    headers: {
        Authorization: `Bearer ${process.env.OLLAMA_API_KEY}`
    }
});

async function chat(message) {
    console.log('🤖 GPT-OSS 120B:', end='');
    
    const response = await ollama.chat({
        model: "gpt-oss:120b",
        messages: [{ role: "user", content: message }],
        stream: true,
    });

    for await (const part of response) {
        process.stdout.write(part.message.content);
    }
    console.log('\n' + '='.repeat(50));
}

// Test
chat("Explain quantum computing simply");