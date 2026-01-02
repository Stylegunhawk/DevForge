"""Language profiles for cheat sheet generation."""

LANGUAGE_PROFILES = {
    "python": {
        "name": "Python",
        "extension": "py",
        "comment": "#",
        "topics": {
            "beginner": [
                "Variables & Types",
                "Basic Math",
                "Strings",
                "Lists",
                "If Statements",
                "Loops (For/While)",
                "Functions"
            ],
            "intermediate": [
                "Dictionaries",
                "Sets",
                "File I/O",
                "Exception Handling",
                "List Comprehensions",
                "Classes & Objects",
                "Modules & Imports"
            ],
            "expert": [
                "Decorators",
                "Generators",
                "Context Managers",
                "Metaclasses",
                "Async/Await",
                "Type Hinting",
                "Multiprocessing"
            ]
        },
        "syntax": {
            "variable": "name = value",
            "function": "def name(args):",
            "class": "class Name:",
            "print": "print(value)"
        }
    },
    "javascript": {
        "name": "JavaScript",
        "extension": "js",
        "comment": "//",
        "topics": {
            "beginner": [
                "Variables (let/const)",
                "Data Types",
                "Operators",
                "Arrays",
                "Conditionals",
                "Loops",
                "Functions"
            ],
            "intermediate": [
                "Objects",
                "DOM Manipulation",
                "Events",
                "Promises",
                "Arrow Functions",
                "Destructuring",
                "Modules"
            ],
            "expert": [
                "Closures",
                "Prototypes",
                "Async/Await",
                "Generators",
                "Proxy & Reflect",
                "Web Workers",
                "Performance"
            ]
        },
        "syntax": {
            "variable": "const name = value;",
            "function": "function name(args) { }",
            "class": "class Name { }",
            "print": "console.log(value);"
        }
    },
    "typescript": {
        "name": "TypeScript",
        "extension": "ts",
        "comment": "//",
        "topics": {
            "beginner": [
                "Basic Types",
                "Interfaces",
                "Functions",
                "Arrays",
                "Enums"
            ],
            "intermediate": [
                "Classes",
                "Generics",
                "Union & Intersection",
                "Type Aliases",
                "Modules"
            ],
            "expert": [
                "Advanced Types",
                "Decorators",
                "Utility Types",
                "Mixins",
                "Declaration Merging"
            ]
        },
        "syntax": {
            "variable": "const name: type = value;",
            "function": "function name(args: type): type { }",
            "class": "class Name { }",
            "print": "console.log(value);"
        }
    }
}
