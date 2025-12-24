"""JavaScript and TypeScript templates for cheatsheet tool"""

# Base JavaScript templates
JAVASCRIPT_BASE = {
    'variables': {
        'title': 'Variables & Data Types',
        'explanation': 'Modern JS variable declarations',
        'examples': [
            {
                'title': 'Let vs Const',
                'code': '''// Mutable - block scoped
let count = 0;
count++;

// Immutable ref - block scoped
const name = "Alice";
// name = "Bob"; // Error

// Arrays/Objects with const are mutable content
const user = { name: "Alice" };
user.name = "Bob"; // OK'''
            },
            {
                'title': 'Arrow Functions',
                'code': '''// Concise syntax
const add = (a, b) => a + b;

// Implicit return with expression
const double = x => x * 2;

// With block body (needs return)
const greet = (name) => {
  return `Hello ${name}`;
};'''
            }
        ],
        'pitfalls': [
            "Avoid `var` (function scope, hoisting issues)",
            "`const` is not immutable value, just immutable binding",
            "Arrow functions don't bind their own `this`"
        ]
    },
    'async_flow': {
        'title': 'Async / Promisies',
        'explanation': 'Handling asynchronous operations',
        'examples': [
            {
                'title': 'Async / Await',
                'code': '''async function fetchData() {
  try {
    const res = await fetch('/api/data');
    const data = await res.json();
    return data;
  } catch (error) {
    console.error('Failed:', error);
  }
}'''
            },
            {
                'title': 'Promises',
                'code': '''fetch('/api/user')
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));'''
            }
        ],
        'pitfalls': [
            "Always wrap `await` in `try/catch`",
            "Don't mix await with `.then()` chains unnecessarily"
        ]
    }
}

# Base TypeScript templates
TYPESCRIPT_BASE = {
    'typing': {
        'title': 'Types & Interfaces',
        'explanation': 'Static typing for JavaScript',
        'examples': [
            {
                'title': 'Interfaces vs Types',
                'code': '''// Interface (better for objects/extending)
interface User {
  id: number;
  name: str;
  email?: str; // Optional
}

// Type (better for unions/primitives)
type Status = 'active' | 'inactive';
type ID = string | number;'''
            },
            {
                'title': 'Generics',
                'code': '''function wrap<T>(value: T): { value: T } {
  return { value };
}

const num = wrap(42); // T is number
const str = wrap("hi"); // T is string'''
            }
        ],
        'pitfalls': [
            "Don't use `any` unless absolutely necessary (use `unknown` safe alternative)",
            "Interfaces are open for merging, Types are closed"
        ]
    }
}

# Merging with JS base for full TS coverage is handled by selector logic or manual merge below
# For simplicity, TS includes JS base + typing section usually, but we keep them separate sets here.

# Ecosystem Templates
JS_LIBRARY_SECTIONS = {
    'react': {
        'beginner': {
            'title': 'React Hooks (Basic)',
            'source_library': 'react',
            'explanation': 'Manage state and side effects',
            'examples': [
                {
                    'title': 'useState',
                    'code': '''import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);

  return (
    <button onClick={() => setCount(c => c + 1)}>
      {count}
    </button>
  );
}'''
                },
                {
                    'title': 'useEffect',
                    'code': '''import { useEffect } from 'react';

function UserData({ id }) {
  useEffect(() => {
    // Runs on mount & when id changes
    fetchUserData(id);
    
    // Cleanup on unmount/re-run
    return () => console.log('Cleanup');
  }, [id]); // Dependency array
}'''
                }
            ],
            'pitfalls': [
                "Always verify dependency array in `useEffect`, `useMemo`",
                "Hooks must be called at top level (not in loops/ifs)",
                "State updates are asynchronous (batched)"
            ]
        }
    },
    'express': {
        'intermediate': {
            'title': 'Express Server',
            'source_library': 'express',
            'explanation': 'Node.js web framework',
            'examples': [
                {
                    'title': 'Basic Server',
                    'code': '''const express = require('express');
const app = express();

// Middleware
app.use(express.json());

// Routes
app.get('/api/users', (req, res) => {
  res.json({ users: [] });
});

app.post('/api/users', (req, res) => {
  const user = req.body;
  // db.save(user)
  res.status(201).json(user);
});

app.listen(3000, () => console.log('Running on 3000'));'''
                }
            ],
            'pitfalls': [
                "Don't forget `next()` in custom middleware",
                "Order of middleware matters",
                "Async errors need `next(err)` or express-async-errors lib"
            ]
        }
    },
    'axios': {
        'intermediate': {
            'title': 'Axios Requests',
            'source_library': 'axios',
            'explanation': 'Promise based HTTP client',
            'examples': [
                {
                    'title': 'GET & POST',
                    'code': '''import axios from 'axios';

// GET
const res = await axios.get('/user?ID=123');

// POST
const res = await axios.post('/user', {
  firstName: 'Fred',
  lastName: 'Flintstone'
});'''
                }
            ],
            'pitfalls': []
        }
    }
}
