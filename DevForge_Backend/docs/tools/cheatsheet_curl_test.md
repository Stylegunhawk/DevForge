1. curl -s -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "code_context": "def f(x): return x*x\nfor i in range(5): print(i)"
    }
  }' | jq .
{
  "success": true,
  "data": {
    "success": true,
    "language": "python",
    "skill_level": "beginner",
    "markdown": "# Python Cheat Sheet - Beginner\n\n\n## 1. Variables & Types\nStore data in named containers\n\n### Basic Types\n```python\n# String\nname = \"Alice\"\nprint(type(name))  # <class 'str'>\n\n# Integer\nage = 25\nprint(type(age))  # <class 'int'>\n\n# Float\nprice = 19.99\nprint(type(price))  # <class 'float'>\n\n# Boolean\nis_active = True\nprint(type(is_active))  # <class 'bool'>\n```\n\n### Type Checking\n```python\n# Check type\nx = 42\nif isinstance(x, int):\n    print(\"x is an integer\")\n\n# Convert types\nnum_str = \"123\"\nnum_int = int(num_str)\nprint(num_int + 10)  # 133\n```\n\n### Common Pitfalls\n- Variable names are case-sensitive: `Name` ≠ `name`\n- Don't use reserved keywords: `class`, `def`, `if`, etc.\n- Use descriptive names: `user_count` not `uc`\n\n\n## 2. Control Flow\nControl program execution with conditions and loops\n\n### If Statements\n```python\nage = 18\n\nif age >= 18:\n    print(\"Adult\")\nelif age >= 13:\n    print(\"Teenager\")\nelse:\n    print(\"Child\")\n\n# Inline if\nstatus = \"adult\" if age >= 18 else \"minor\"\n```\n\n### For Loops\n```python\n# Loop through range\nfor i in range(5):\n    print(i)  # 0, 1, 2, 3, 4\n\n# Loop through list\nfruits = ['apple', 'banana', 'orange']\nfor fruit in fruits:\n    print(fruit)\n\n# Loop with index\nfor i, fruit in enumerate(fruits):\n    print(f\"{i}: {fruit}\")\n```\n\n### Common Pitfalls\n- Indentation matters - use 4 spaces\n- Use `elif`, not `else if`\n- `range(5)` goes from 0 to 4, not 1 to 5\n\n\n## 3. Functions\nReusable blocks of code\n\n### Basic Function\n```python\ndef greet(name):\n    \"\"\"Say hello to someone\"\"\"\n    return f\"Hello, {name}!\"\n\nresult = greet(\"Alice\")\nprint(result)  # Hello, Alice!\n```\n\n### Multiple Parameters\n```python\ndef add(a, b):\n    \"\"\"Add two numbers\"\"\"\n    return a + b\n\n# Positional arguments\ntotal = add(5, 3)\nprint(total)  # 8\n\n# Keyword arguments\ntotal = add(a=10, b=20)\nprint(total)  # 30\n```\n\n### Common Pitfalls\n- Always include docstrings for functions\n- Use `return` to send values back\n- Default arguments must come after required ones\n\n\n## Quick Reference\n\n| Task | Code |\n|---|---|\n| Print to console | `print(value)` |\n| Define variable | `name = value` |\n| Define function | `def name(args):` |\n| If statement | `if condition:` |\n| For loop | `for x in items:` |\n| Import module | `import module` |",
    "data": {
      "language": "Python",
      "skill_level": "beginner",
      "detected_libraries": [],
      "supported_libraries": [],
      "complexity_score": 3,
      "sections": [
        {
          "title": "Variables & Types"
        },
        {
          "title": "Control Flow"
        },
        {
          "title": "Functions"
        }
      ],
      "enrichment": {
        "enabled": false,
        "reason": "feature_disabled",
        "enriched_sections": [],
        "target_libraries": [],
        "confidence": 0.0,
        "promotable": false
      },
      "method": "template",
      "response_time_ms": 2
    }
  },
  "message": "generate_cheatsheet executed successfully"
}

2. curl -s -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "code_context": "import pandas as pd\ndf = pd.read_csv(\"data.csv\")\ndf.groupby(\"id\").sum()",
      "skill_level": "intermediate"
    }
  }' | jq .
{
  "success": true,
  "data": {
    "success": true,
    "language": "python",
    "skill_level": "intermediate",
    "markdown": "# Python Cheat Sheet - Intermediate\n\n\n## 1. Pandas DataFrames\nEfficiently manipulate tabular data\n\n### Loading & Inspecting\n```python\nimport pandas as pd\n\n# Load CSV\ndf = pd.read_csv('data.csv')\n\n# Inspect\nprint(df.head())  # First 5 rows\nprint(df.info())  # Column types\nprint(df.describe())  # Statistics\n```\n\n### Filtering & Selection\n```python\n# Select columns\nnames = df['name']\nsubset = df[['name', 'age']]\n\n# Filter rows\nadults = df[df['age'] >= 18]\n\n# Multiple conditions\nny_adults = df[(df['age'] >= 18) & (df['city'] == 'NYC')]\n```\n\n### Grouping & Aggregation\n```python\n# Group by single column\navg_by_city = df.groupby('city')['age'].mean()\n\n# Multiple aggregations\nsummary = df.groupby('city').agg({\n    'age': ['mean', 'max', 'min'],\n    'salary': 'sum'\n})\n\n# Reset index\nsummary = summary.reset_index()\n```\n\n### Common Pitfalls\n- Use `.copy()` to avoid SettingWithCopyWarning\n- Chain operations for readability: `df.query().sort_values()`\n- `.loc[]` for label-based, `.iloc[]` for position-based indexing\n\n\n## 2. Data Structures\nBuilt-in collections for organizing data\n\n### Lists & Tuples\n```python\n# Lists (mutable)\nfruits = ['apple', 'banana', 'cherry']\nfruits.append('orange')\nfruits.extend(['grape', 'mango'])\nfruits.remove('banana')\n\n# List slicing\nfirst_two = fruits[:2]\nlast_item = fruits[-1]\n\n# Tuples (immutable)\ncoordinates = (10, 20)\nx, y = coordinates  # Unpacking\n```\n\n### Dictionaries & Sets\n```python\n# Dictionaries\nuser = {'name': 'Alice', 'age': 25, 'city': 'NYC'}\nuser['email'] = 'alice@example.com'\nuser.update({'age': 26, 'country': 'USA'})\n\n# Dict methods\nkeys = user.keys()\nvalues = user.values()\nitems = user.items()\n\n# Sets (unique elements)\ntags = {'python', 'data', 'api'}\ntags.add('web')\ntags.discard('data')\n```\n\n### Common Pitfalls\n- Lists are mutable, tuples are immutable\n- Dict keys must be immutable (strings, numbers, tuples)\n- Sets don't maintain order (use dict for ordered unique values)\n\n\n## 3. File I/O\nRead and write files efficiently\n\n### Text Files\n```python\n# Reading\nwith open('data.txt', 'r') as f:\n    content = f.read()  # Entire file\n    # OR\n    lines = f.readlines()  # List of lines\n\n# Writing\nwith open('output.txt', 'w') as f:\n    f.write('Hello\\n')\n    f.writelines(['Line 1\\n', 'Line 2\\n'])\n\n# Appending\nwith open('log.txt', 'a') as f:\n    f.write('New entry\\n')\n```\n\n### JSON & CSV\n```python\nimport json\nimport csv\n\n# JSON\ndata = {'name': 'Alice', 'scores': [95, 87, 92]}\nwith open('data.json', 'w') as f:\n    json.dump(data, f, indent=2)\n\nwith open('data.json', 'r') as f:\n    loaded = json.load(f)\n\n# CSV\nwith open('data.csv', 'w', newline='') as f:\n    writer = csv.writer(f)\n    writer.writerow(['Name', 'Age'])\n    writer.writerow(['Alice', 25])\n```\n\n### Common Pitfalls\n- Always use `with` statement for automatic file closing\n- Use `'r'` for read, `'w'` for write (overwrites), `'a'` for append\n- JSON requires double quotes for strings\n\n\n## 4. Error Handling\nHandle errors gracefully\n\n### Try-Except Basics\n```python\n# Basic error handling\ntry:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print(\"Cannot divide by zero\")\n    result = None\n\n# Multiple exceptions\ntry:\n    value = int(input(\"Enter number: \"))\n    result = 10 / value\nexcept ValueError:\n    print(\"Invalid number\")\nexcept ZeroDivisionError:\n    print(\"Cannot divide by zero\")\nfinally:\n    print(\"Cleanup here\")\n```\n\n### Custom Exceptions\n```python\n# Define custom exception\nclass InvalidAgeError(Exception):\n    def __init__(self, age):\n        self.age = age\n        super().__init__(f\"Age {age} is invalid\")\n\n# Use custom exception\ndef validate_age(age):\n    if age < 0 or age > 120:\n        raise InvalidAgeError(age)\n    return True\n\ntry:\n    validate_age(150)\nexcept InvalidAgeError as e:\n    print(f\"Error: {e}\")\n```\n\n### Common Pitfalls\n- Don't use bare `except:` - catch specific exceptions\n- `finally` runs even if exception occurs\n- Use custom exceptions for domain-specific errors\n\n\n## 5. Modules & Packages\nOrganize code into reusable modules\n\n### Import Styles\n```python\n# Import entire module\nimport os\npath = os.path.join('folder', 'file.txt')\n\n# Import specific functions\nfrom os.path import join, exists\nif exists('data.txt'):\n    print(\"File exists\")\n\n# Import with alias\nimport numpy as np\narray = np.array([1, 2, 3])\n\n# Import all (avoid in production)\nfrom math import *  # Not recommended\n```\n\n### Creating Packages\n```python\n# Project structure:\n# mypackage/\n#   __init__.py\n#   module1.py\n#   module2.py\n\n# mypackage/__init__.py\nfrom .module1 import func1\nfrom .module2 import func2\n\n__all__ = ['func1', 'func2']\n__version__ = '1.0.0'\n\n# Usage\nfrom mypackage import func1\nresult = func1()\n```\n\n### Common Pitfalls\n- `__init__.py` makes directory a package\n- Use relative imports (`.module`) within packages\n- Circular imports cause errors - restructure code\n\n\n## Quick Reference\n\n| Pattern | Code | Use Case |\n|---|---|---|\n| Load CSV | `pd.read_csv(\"file.csv\")` | DataFrame I/O |\n| Filter rows | `df[df[\"col\"] > 10]` | Boolean indexing |\n| Group & aggregate | `df.groupby(\"col\").mean()` | Summarize data |\n| List comprehension | `[x*2 for x in items]` | Transform lists |\n| Dict comprehension | `{k: v*2 for k, v in d.items()}` | Transform dicts |\n| Lambda function | `lambda x: x*2` | Anonymous function |",
    "data": {
      "language": "Python",
      "skill_level": "intermediate",
      "detected_libraries": [
        "pandas"
      ],
      "supported_libraries": [
        "pandas"
      ],
      "complexity_score": 2,
      "sections": [
        {
          "title": "Pandas DataFrames"
        },
        {
          "title": "Data Structures"
        },
        {
          "title": "File I/O"
        },
        {
          "title": "Error Handling"
        },
        {
          "title": "Modules & Packages"
        }
      ],
      "enrichment": {
        "enabled": false,
        "reason": "feature_disabled",
        "enriched_sections": [],
        "target_libraries": [],
        "confidence": 0.0,
        "promotable": false
      },
      "method": "template",
      "response_time_ms": 0
    }
  },
  "message": "generate_cheatsheet executed successfully"
}

3. curl -s -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "code_context": "from langchain.graphs import StateGraph\ngraph = StateGraph()",
      "conversation_history": "Show me the latest LangGraph patterns",
      "skill_level": "intermediate"
    }
  }' | jq .
{
  "success": true,
  "data": {
    "success": true,
    "language": "python",
    "skill_level": "intermediate",
    "markdown": "# Python Cheat Sheet - Intermediate\n\n\n## 1. LangChain Basics\nBuild LLM-powered applications (Enriched by AI)\n\n### Basic Chain\n```python\n# This section will be enriched with latest examples\n```\n\n\n## 2. LangGraph Workflows\nBuild stateful, multi-actor applications (Enriched by AI)\n\n### State Graph\n```python\n# This section will be enriched with latest examples\n```\n\n\n## 3. Data Structures\nBuilt-in collections for organizing data\n\n### Lists & Tuples\n```python\n# Lists (mutable)\nfruits = ['apple', 'banana', 'cherry']\nfruits.append('orange')\nfruits.extend(['grape', 'mango'])\nfruits.remove('banana')\n\n# List slicing\nfirst_two = fruits[:2]\nlast_item = fruits[-1]\n\n# Tuples (immutable)\ncoordinates = (10, 20)\nx, y = coordinates  # Unpacking\n```\n\n### Dictionaries & Sets\n```python\n# Dictionaries\nuser = {'name': 'Alice', 'age': 25, 'city': 'NYC'}\nuser['email'] = 'alice@example.com'\nuser.update({'age': 26, 'country': 'USA'})\n\n# Dict methods\nkeys = user.keys()\nvalues = user.values()\nitems = user.items()\n\n# Sets (unique elements)\ntags = {'python', 'data', 'api'}\ntags.add('web')\ntags.discard('data')\n```\n\n### Common Pitfalls\n- Lists are mutable, tuples are immutable\n- Dict keys must be immutable (strings, numbers, tuples)\n- Sets don't maintain order (use dict for ordered unique values)\n\n\n## 4. File I/O\nRead and write files efficiently\n\n### Text Files\n```python\n# Reading\nwith open('data.txt', 'r') as f:\n    content = f.read()  # Entire file\n    # OR\n    lines = f.readlines()  # List of lines\n\n# Writing\nwith open('output.txt', 'w') as f:\n    f.write('Hello\\n')\n    f.writelines(['Line 1\\n', 'Line 2\\n'])\n\n# Appending\nwith open('log.txt', 'a') as f:\n    f.write('New entry\\n')\n```\n\n### JSON & CSV\n```python\nimport json\nimport csv\n\n# JSON\ndata = {'name': 'Alice', 'scores': [95, 87, 92]}\nwith open('data.json', 'w') as f:\n    json.dump(data, f, indent=2)\n\nwith open('data.json', 'r') as f:\n    loaded = json.load(f)\n\n# CSV\nwith open('data.csv', 'w', newline='') as f:\n    writer = csv.writer(f)\n    writer.writerow(['Name', 'Age'])\n    writer.writerow(['Alice', 25])\n```\n\n### Common Pitfalls\n- Always use `with` statement for automatic file closing\n- Use `'r'` for read, `'w'` for write (overwrites), `'a'` for append\n- JSON requires double quotes for strings\n\n\n## 5. Error Handling\nHandle errors gracefully\n\n### Try-Except Basics\n```python\n# Basic error handling\ntry:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print(\"Cannot divide by zero\")\n    result = None\n\n# Multiple exceptions\ntry:\n    value = int(input(\"Enter number: \"))\n    result = 10 / value\nexcept ValueError:\n    print(\"Invalid number\")\nexcept ZeroDivisionError:\n    print(\"Cannot divide by zero\")\nfinally:\n    print(\"Cleanup here\")\n```\n\n### Custom Exceptions\n```python\n# Define custom exception\nclass InvalidAgeError(Exception):\n    def __init__(self, age):\n        self.age = age\n        super().__init__(f\"Age {age} is invalid\")\n\n# Use custom exception\ndef validate_age(age):\n    if age < 0 or age > 120:\n        raise InvalidAgeError(age)\n    return True\n\ntry:\n    validate_age(150)\nexcept InvalidAgeError as e:\n    print(f\"Error: {e}\")\n```\n\n### Common Pitfalls\n- Don't use bare `except:` - catch specific exceptions\n- `finally` runs even if exception occurs\n- Use custom exceptions for domain-specific errors\n\n\n## 6. Modules & Packages\nOrganize code into reusable modules\n\n### Import Styles\n```python\n# Import entire module\nimport os\npath = os.path.join('folder', 'file.txt')\n\n# Import specific functions\nfrom os.path import join, exists\nif exists('data.txt'):\n    print(\"File exists\")\n\n# Import with alias\nimport numpy as np\narray = np.array([1, 2, 3])\n\n# Import all (avoid in production)\nfrom math import *  # Not recommended\n```\n\n### Creating Packages\n```python\n# Project structure:\n# mypackage/\n#   __init__.py\n#   module1.py\n#   module2.py\n\n# mypackage/__init__.py\nfrom .module1 import func1\nfrom .module2 import func2\n\n__all__ = ['func1', 'func2']\n__version__ = '1.0.0'\n\n# Usage\nfrom mypackage import func1\nresult = func1()\n```\n\n### Common Pitfalls\n- `__init__.py` makes directory a package\n- Use relative imports (`.module`) within packages\n- Circular imports cause errors - restructure code\n\n\n## Quick Reference\n\n| Pattern | Code | Use Case |\n|---|---|---|\n| List comprehension | `[x*2 for x in items]` | Transform lists |\n| Dict comprehension | `{k: v*2 for k, v in d.items()}` | Transform dicts |\n| Lambda function | `lambda x: x*2` | Anonymous function |",
    "data": {
      "language": "Python",
      "skill_level": "intermediate",
      "detected_libraries": [
        "langchain",
        "langgraph"
      ],
      "supported_libraries": [
        "langchain",
        "langgraph"
      ],
      "complexity_score": 2,
      "sections": [
        {
          "title": "LangChain Basics"
        },
        {
          "title": "LangGraph Workflows"
        },
        {
          "title": "Data Structures"
        },
        {
          "title": "File I/O"
        },
        {
          "title": "Error Handling"
        },
        {
          "title": "Modules & Packages"
        }
      ],
      "enrichment": {
        "enabled": false,
        "reason": "feature_disabled",
        "enriched_sections": [],
        "target_libraries": [],
        "confidence": 0.0,
        "promotable": false
      },
      "method": "template",
      "response_time_ms": 0
    }
  },
  "message": "generate_cheatsheet executed successfully"
}

4. curl -s -X POST http://localhost:8000/api/gateway \
  -H "Content-Type: application/json" \
  -d '{
    "name": "generate_cheatsheet",
    "arguments": {
      "code_context": "import React from \"react\"\nuseEffect(() => {})",
      "conversation_history": "latest react patterns"
    }
  }' | jq .
{
  "success": true,
  "data": {
    "success": true,
    "language": "python",
    "skill_level": "beginner",
    "markdown": "# Python Cheat Sheet - Beginner\n\n\n## 1. React Hooks (Basic)\nManage state and side effects\n\n### useState\n```python\nimport { useState } from 'react';\n\nfunction Counter() {\n  const [count, setCount] = useState(0);\n\n  return (\n    <button onClick={() => setCount(c => c + 1)}>\n      {count}\n    </button>\n  );\n}\n```\n\n### useEffect\n```python\nimport { useEffect } from 'react';\n\nfunction UserData({ id }) {\n  useEffect(() => {\n    // Runs on mount & when id changes\n    fetchUserData(id);\n    \n    // Cleanup on unmount/re-run\n    return () => console.log('Cleanup');\n  }, [id]); // Dependency array\n}\n```\n\n### Common Pitfalls\n- Always verify dependency array in `useEffect`, `useMemo`\n- Hooks must be called at top level (not in loops/ifs)\n- State updates are asynchronous (batched)\n\n\n## 2. Variables & Types\nStore data in named containers\n\n### Basic Types\n```python\n# String\nname = \"Alice\"\nprint(type(name))  # <class 'str'>\n\n# Integer\nage = 25\nprint(type(age))  # <class 'int'>\n\n# Float\nprice = 19.99\nprint(type(price))  # <class 'float'>\n\n# Boolean\nis_active = True\nprint(type(is_active))  # <class 'bool'>\n```\n\n### Type Checking\n```python\n# Check type\nx = 42\nif isinstance(x, int):\n    print(\"x is an integer\")\n\n# Convert types\nnum_str = \"123\"\nnum_int = int(num_str)\nprint(num_int + 10)  # 133\n```\n\n### Common Pitfalls\n- Variable names are case-sensitive: `Name` ≠ `name`\n- Don't use reserved keywords: `class`, `def`, `if`, etc.\n- Use descriptive names: `user_count` not `uc`\n\n\n## 3. Control Flow\nControl program execution with conditions and loops\n\n### If Statements\n```python\nage = 18\n\nif age >= 18:\n    print(\"Adult\")\nelif age >= 13:\n    print(\"Teenager\")\nelse:\n    print(\"Child\")\n\n# Inline if\nstatus = \"adult\" if age >= 18 else \"minor\"\n```\n\n### For Loops\n```python\n# Loop through range\nfor i in range(5):\n    print(i)  # 0, 1, 2, 3, 4\n\n# Loop through list\nfruits = ['apple', 'banana', 'orange']\nfor fruit in fruits:\n    print(fruit)\n\n# Loop with index\nfor i, fruit in enumerate(fruits):\n    print(f\"{i}: {fruit}\")\n```\n\n### Common Pitfalls\n- Indentation matters - use 4 spaces\n- Use `elif`, not `else if`\n- `range(5)` goes from 0 to 4, not 1 to 5\n\n\n## 4. Functions\nReusable blocks of code\n\n### Basic Function\n```python\ndef greet(name):\n    \"\"\"Say hello to someone\"\"\"\n    return f\"Hello, {name}!\"\n\nresult = greet(\"Alice\")\nprint(result)  # Hello, Alice!\n```\n\n### Multiple Parameters\n```python\ndef add(a, b):\n    \"\"\"Add two numbers\"\"\"\n    return a + b\n\n# Positional arguments\ntotal = add(5, 3)\nprint(total)  # 8\n\n# Keyword arguments\ntotal = add(a=10, b=20)\nprint(total)  # 30\n```\n\n### Common Pitfalls\n- Always include docstrings for functions\n- Use `return` to send values back\n- Default arguments must come after required ones\n\n\n## Quick Reference\n\n| Task | Code |\n|---|---|\n| Print to console | `print(value)` |\n| Define variable | `name = value` |\n| Define function | `def name(args):` |\n| If statement | `if condition:` |\n| For loop | `for x in items:` |\n| Import module | `import module` |",
    "data": {
      "language": "Python",
      "skill_level": "beginner",
      "detected_libraries": [
        "react"
      ],
      "supported_libraries": [
        "react"
      ],
      "complexity_score": 2,
      "sections": [
        {
          "title": "React Hooks (Basic)"
        },
        {
          "title": "Variables & Types"
        },
        {
          "title": "Control Flow"
        },
        {
          "title": "Functions"
        }
      ],
      "enrichment": {
        "enabled": false,
        "reason": "feature_disabled",
        "enriched_sections": [],
        "target_libraries": [],
        "confidence": 0.0,
        "promotable": false
      },
      "method": "template",
      "response_time_ms": 0
    }
  },
  "message": "generate_cheatsheet executed successfully"
}

5. curl -s http://localhost:8000/api/admin/promotions | jq .
{
  "total_enrichments": 0,
  "candidates": []
} 

6. 