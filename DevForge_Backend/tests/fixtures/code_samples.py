"""Test fixtures for cheatsheet enhancement testing"""

# Simple beginner code
SAMPLE_SIMPLE = "// python\ndef add(a, b):\n    return a + b"

# Single library - pandas
SAMPLE_PANDAS = """// python
import pandas as pd
df = pd.read_csv('data.csv')
df['total'] = df['price'] * df['quantity']
result = df.groupby('category')['total'].mean()
"""

# Multi-library - FastAPI + Pydantic
SAMPLE_FASTAPI = """// python
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.post("/items/")
async def create_item(item: Item):
    return {"item": item.name, "price": item.price}
"""

# Complex async code
SAMPLE_ASYNC = """// python
import asyncio
import aiohttp

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def main():
    urls = ['http://example.com'] * 10
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
"""

# Multi-block context (frontend format)
SAMPLE_MULTI_BLOCK = """// python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

---

// python
class DataProcessor:
    def __init__(self, data):
        self.data = data
    
    def process(self):
        return [x**2 for x in self.data]
"""

# Edge cases
SAMPLE_EMPTY = ""
SAMPLE_NO_SEPARATOR = "// python\nprint('hello')"
