"""Enhanced templates with real code examples"""

# Base templates for beginner level
PYTHON_BEGINNER_BASE = {
    'variables': {
        'title': 'Variables & Types',
        'explanation': 'Store data in named containers',
        'examples': [
            {
                'title': 'Basic Types',
                'code': '''# String
name = "Alice"
print(type(name))  # <class 'str'>

# Integer
age = 25
print(type(age))  # <class 'int'>

# Float
price = 19.99
print(type(price))  # <class 'float'>

# Boolean
is_active = True
print(type(is_active))  # <class 'bool'>'''
            },
            {
                'title': 'Type Checking',
                'code': '''# Check type
x = 42
if isinstance(x, int):
    print("x is an integer")

# Convert types
num_str = "123"
num_int = int(num_str)
print(num_int + 10)  # 133'''
            }
        ],
        'pitfalls': [
            "Variable names are case-sensitive: `Name` ≠ `name`",
            "Don't use reserved keywords: `class`, `def`, `if`, etc.",
            "Use descriptive names: `user_count` not `uc`"
        ]
    },
    'control_flow': {
        'title': 'Control Flow',
        'explanation': 'Control program execution with conditions and loops',
        'examples': [
            {
                'title': 'If Statements',
                'code': '''age = 18

if age >= 18:
    print("Adult")
elif age >= 13:
    print("Teenager")
else:
    print("Child")

# Inline if
status = "adult" if age >= 18 else "minor"'''
            },
            {
                'title': 'For Loops',
                'code': '''# Loop through range
for i in range(5):
    print(i)  # 0, 1, 2, 3, 4

# Loop through list
fruits = ['apple', 'banana', 'orange']
for fruit in fruits:
    print(fruit)

# Loop with index
for i, fruit in enumerate(fruits):
    print(f"{i}: {fruit}")'''
            }
        ],
        'pitfalls': [
            "Indentation matters - use 4 spaces",
            "Use `elif`, not `else if`",
            "`range(5)` goes from 0 to 4, not 1 to 5"
        ]
    },
    'functions': {
        'title': 'Functions',
        'explanation': 'Reusable blocks of code',
        'examples': [
            {
                'title': 'Basic Function',
                'code': '''def greet(name):
    """Say hello to someone"""
    return f"Hello, {name}!"

result = greet("Alice")
print(result)  # Hello, Alice!'''
            },
            {
                'title': 'Multiple Parameters',
                'code': '''def add(a, b):
    """Add two numbers"""
    return a + b

# Positional arguments
total = add(5, 3)
print(total)  # 8

# Keyword arguments
total = add(a=10, b=20)
print(total)  # 30'''
            }
        ],
        'pitfalls': [
            "Always include docstrings for functions",
            "Use `return` to send values back",
            "Default arguments must come after required ones"
        ]
    }
}

# Intermediate templates
PYTHON_INTERMEDIATE_BASE = {
    'data_structures': {
        'title': 'Data Structures',
        'explanation': 'Built-in collections for organizing data',
        'examples': [
            {
                'title': 'Lists & Tuples',
                'code': '''# Lists (mutable)
fruits = ['apple', 'banana', 'cherry']
fruits.append('orange')
fruits.extend(['grape', 'mango'])
fruits.remove('banana')

# List slicing
first_two = fruits[:2]
last_item = fruits[-1]

# Tuples (immutable)
coordinates = (10, 20)
x, y = coordinates  # Unpacking'''
            },
            {
                'title': 'Dictionaries & Sets',
                'code': '''# Dictionaries
user = {'name': 'Alice', 'age': 25, 'city': 'NYC'}
user['email'] = 'alice@example.com'
user.update({'age': 26, 'country': 'USA'})

# Dict methods
keys = user.keys()
values = user.values()
items = user.items()

# Sets (unique elements)
tags = {'python', 'data', 'api'}
tags.add('web')
tags.discard('data')'''
            }
        ],
        'pitfalls': [
            "Lists are mutable, tuples are immutable",
            "Dict keys must be immutable (strings, numbers, tuples)",
            "Sets don't maintain order (use dict for ordered unique values)"
        ]
    },
    'file_io': {
        'title': 'File I/O',
        'explanation': 'Read and write files efficiently',
        'examples': [
            {
                'title': 'Text Files',
                'code': '''# Reading
with open('data.txt', 'r') as f:
    content = f.read()  # Entire file
    # OR
    lines = f.readlines()  # List of lines

# Writing
with open('output.txt', 'w') as f:
    f.write('Hello\\n')
    f.writelines(['Line 1\\n', 'Line 2\\n'])

# Appending
with open('log.txt', 'a') as f:
    f.write('New entry\\n')'''
            },
            {
                'title': 'JSON & CSV',
                'code': '''import json
import csv

# JSON
data = {'name': 'Alice', 'scores': [95, 87, 92]}
with open('data.json', 'w') as f:
    json.dump(data, f, indent=2)

with open('data.json', 'r') as f:
    loaded = json.load(f)

# CSV
with open('data.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Name', 'Age'])
    writer.writerow(['Alice', 25])'''
            }
        ],
        'pitfalls': [
            "Always use `with` statement for automatic file closing",
            "Use `'r'` for read, `'w'` for write (overwrites), `'a'` for append",
            "JSON requires double quotes for strings"
        ]
    },
    'error_handling': {
        'title': 'Error Handling',
        'explanation': 'Handle errors gracefully',
        'examples': [
            {
                'title': 'Try-Except Basics',
                'code': '''# Basic error handling
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero")
    result = None

# Multiple exceptions
try:
    value = int(input("Enter number: "))
    result = 10 / value
except ValueError:
    print("Invalid number")
except ZeroDivisionError:
    print("Cannot divide by zero")
finally:
    print("Cleanup here")'''
            },
            {
                'title': 'Custom Exceptions',
                'code': '''# Define custom exception
class InvalidAgeError(Exception):
    def __init__(self, age):
        self.age = age
        super().__init__(f"Age {age} is invalid")

# Use custom exception
def validate_age(age):
    if age < 0 or age > 120:
        raise InvalidAgeError(age)
    return True

try:
    validate_age(150)
except InvalidAgeError as e:
    print(f"Error: {e}")'''
            }
        ],
        'pitfalls': [
            "Don't use bare `except:` - catch specific exceptions",
            "`finally` runs even if exception occurs",
            "Use custom exceptions for domain-specific errors"
        ]
    },
    'modules': {
        'title': 'Modules & Packages',
        'explanation': 'Organize code into reusable modules',
        'examples': [
            {
                'title': 'Import Styles',
                'code': '''# Import entire module
import os
path = os.path.join('folder', 'file.txt')

# Import specific functions
from os.path import join, exists
if exists('data.txt'):
    print("File exists")

# Import with alias
import numpy as np
array = np.array([1, 2, 3])

# Import all (avoid in production)
from math import *  # Not recommended'''
            },
            {
                'title': 'Creating Packages',
                'code': '''# Project structure:
# mypackage/
#   __init__.py
#   module1.py
#   module2.py

# mypackage/__init__.py
from .module1 import func1
from .module2 import func2

__all__ = ['func1', 'func2']
__version__ = '1.0.0'

# Usage
from mypackage import func1
result = func1()'''
            }
        ],
        'pitfalls': [
            "`__init__.py` makes directory a package",
            "Use relative imports (`.module`) within packages",
            "Circular imports cause errors - restructure code"
        ]
    }
}

# Expert templates
PYTHON_EXPERT_BASE = {
    'decorators': {
        'title': 'Decorators',
        'explanation': 'Modify function behavior without changing code',
        'examples': [
            {
                'title': 'Built-in Decorators',
                'code': '''class User:
    def __init__(self, name, age):
        self._name = name
        self._age = age
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        if not value:
            raise ValueError("Name required")
        self._name = value
    
    @staticmethod
    def is_adult(age):
        return age >= 18
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['name'], data['age'])'''
            },
            {
                'title': 'Custom Decorators',
                'code': '''import time
from functools import wraps

# Simple decorator
def timer(func):
    @wraps(func)  # Preserve function metadata
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time()-start:.2f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "Done"

result = slow_function()  # Prints timing'''
            }
        ],
        'pitfalls': [
            "Use `@wraps` to preserve function metadata",
            "`@property` makes methods look like attributes",
            "Decorators execute at import time, not call time"
        ]
    },
    'generators': {
        'title': 'Generators',
        'explanation': 'Memory-efficient iteration with lazy evaluation',
        'examples': [
            {
                'title': 'Generator Functions',
                'code': '''# Instead of returning list
def large_range(n):
    """Generator for memory efficiency"""
    i = 0
    while i < n:
        yield i
        i += 1

# Usage
for num in large_range(1000000):
    if num > 10:
        break

# Generator with state
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fib = fibonacci()
first_10 = [next(fib) for _ in range(10)]'''
            },
            {
                'title': 'Generator Expressions',
                'code': '''# Like list comprehension but lazy
sum_squares = sum(x**2 for x in range(1000000))

# Processing large files
with open('huge.log', 'r') as f:
    errors = (line for line in f if 'ERROR' in line)
    first_error = next(errors, None)

# Chaining generators
def read_lines(filename):
    with open(filename) as f:
        yield from f

lines = read_lines('data.txt')'''
            }
        ],
        'pitfalls': [
            "Generators can only be iterated once",
            "Use `()` for generator expressions, `[]` for lists",
            "`yield from` delegates to another generator"
        ]
    },
    'context_managers': {
        'title': 'Context Managers',
        'explanation': 'Automatic resource management with `with` statement',
        'examples': [
            {
                'title': 'Class-based Context Manager',
                'code': '''class DatabaseConnection:
    def __init__(self, host):
        self.host = host
        self.conn = None
    
    def __enter__(self):
        print(f"Connecting to {self.host}")
        self.conn = f"Connection to {self.host}"
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Closing connection")
        self.conn = None
        return False  # Don't suppress exceptions

# Usage
with DatabaseConnection('localhost') as conn:
    print(f"Using {conn}")'''
            },
            {
                'title': 'Contextlib Decorator',
                'code': '''from contextlib import contextmanager
import tempfile
import os

@contextmanager
def temporary_directory():
    """Creates temp dir, cleans up after"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        import shutil
        shutil.rmtree(temp_dir)

with temporary_directory() as tmpdir:
    filepath = os.path.join(tmpdir, 'data.txt')
    with open(filepath, 'w') as f:
        f.write('temp data')
# Directory automatically deleted'''
            }
        ],
        'pitfalls': [
            "`__enter__` return value is assigned to `as` variable",
            "`__exit__` return True to suppress exceptions",
            "Use `@contextmanager` for simpler implementation"
        ]
    },
    'classes': {
        'title': 'Advanced Classes',
        'explanation': 'OOP patterns and inheritance',
        'examples': [
            {
                'title': 'Inheritance & Super',
                'code': '''class Animal:
    def __init__(self, name):
        self.name = name
    
    def speak(self):
        return "Some sound"

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name)  # Call parent init
        self.breed = breed
    
    def speak(self):
        return f"{self.name} says Woof!"
    
    def __str__(self):
        return f"Dog({self.name}, {self.breed})"
    
    def __repr__(self):
        return f"Dog(name='{self.name}', breed='{self.breed}')"

dog = Dog("Buddy", "Golden")
print(dog)  # Uses __str__'''
            },
            {
                'title': 'Special Methods',
                'code': '''class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __len__(self):
        return 2
    
    def __getitem__(self, index):
        return [self.x, self.y][index]

v1 = Vector(1, 2)
v2 = Vector(3, 4)
v3 = v1 + v2  # Calls __add__
print(v3[0])  # Calls __getitem__'''
            }
        ],
        'pitfalls': [
            "Use `super()` to call parent methods",
            "`__str__` for users, `__repr__` for developers",
            "Special methods enable operator overloading"
        ]
    }
}

# Library-specific sections
LIBRARY_SECTIONS = {
    'pandas': {
        'intermediate': {
            'title': 'Pandas DataFrames',
            'explanation': 'Efficiently manipulate tabular data',
            'examples': [
                {
                    'title': 'Loading & Inspecting',
                    'code': '''import pandas as pd

# Load CSV
df = pd.read_csv('data.csv')

# Inspect
print(df.head())  # First 5 rows
print(df.info())  # Column types
print(df.describe())  # Statistics'''
                },
                {
                    'title': 'Filtering & Selection',
                    'code': '''# Select columns
names = df['name']
subset = df[['name', 'age']]

# Filter rows
adults = df[df['age'] >= 18]

# Multiple conditions
ny_adults = df[(df['age'] >= 18) & (df['city'] == 'NYC')]'''
                },
                {
                    'title': 'Grouping & Aggregation',
                    'code': '''# Group by single column
avg_by_city = df.groupby('city')['age'].mean()

# Multiple aggregations
summary = df.groupby('city').agg({
    'age': ['mean', 'max', 'min'],
    'salary': 'sum'
})

# Reset index
summary = summary.reset_index()'''
                }
            ],
            'pitfalls': [
                "Use `.copy()` to avoid SettingWithCopyWarning",
                "Chain operations for readability: `df.query().sort_values()`",
                "`.loc[]` for label-based, `.iloc[]` for position-based indexing"
            ],
            'quick_ref': [
                ('Load CSV', 'pd.read_csv("file.csv")', 'Fast for <1M rows'),
                ('Filter', 'df[df["col"] > 10]', 'Returns view'),
                ('Group', 'df.groupby("col").mean()', 'Aggregate by category'),
            ]
        }
    },
    'fastapi': {
        'intermediate': {
            'title': 'FastAPI Routes & Dependencies',
            'explanation': 'Build high-performance async APIs',
            'examples': [
                {
                    'title': 'Basic Routes',
                    'code': '''from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}'''
                },
                {
                    'title': 'Request Body with Pydantic',
                    'code': '''from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = False

@app.post("/items/")
async def create_item(item: Item):
    # Item automatically validated
    return {"name": item.name, "price": item.price}'''
                },
                {
                    'title': 'Dependencies',
                    'code': '''from fastapi import Depends

async def get_db():
    db = Database()
    try:
        yield db
    finally:
        await db.close()

@app.get("/users/")
async def read_users(db = Depends(get_db)):
    return await db.query_users()'''
                }
            ],
            'pitfalls': [
                "Always use `async def` for I/O operations",
                "Validate input with Pydantic, not manual checks",
                "Use `Depends()` for shared resources (DB, auth)"
            ]
        }
    },
    'asyncio': {
        'expert': {
            'title': 'Async/Await Patterns',
            'explanation': 'Concurrent execution with coroutines',
            'examples': [
                {
                    'title': 'Basic Async Function',
                    'code': '''import asyncio

async def fetch_data(id):
    await asyncio.sleep(1)  # Simulate I/O
    return f"Data {id}"

# Run single coroutine
result = asyncio.run(fetch_data(1))
print(result)  # Data 1'''
                },
                {
                    'title': 'Concurrent Execution',
                    'code': '''async def main():
    # Run 3 tasks concurrently
    tasks = [fetch_data(i) for i in range(3)]
    results = await asyncio.gather(*tasks)
    # Completes in ~1s, not 3s
    return results

asyncio.run(main())'''
                },
                {
                    'title': 'Error Handling',
                    'code': '''async def safe_fetch(id):
    try:
        return await fetch_data(id)
    except Exception as e:
        return f"Error: {e}"

# Don't stop on errors
results = await asyncio.gather(
    *tasks,
    return_exceptions=True
)'''
                }
            ],
            'pitfalls': [
                "Never use `time.sleep()` in async code (use `asyncio.sleep()`)",
                "`gather()` returns in order, not completion order",
                "Always `await` coroutines or they won't run"
            ]
        }
    }
}

BASE_TEMPLATES = {
    'python': {
        'beginner': PYTHON_BEGINNER_BASE,
        'intermediate': PYTHON_INTERMEDIATE_BASE,
        'expert': PYTHON_EXPERT_BASE
    }
}
