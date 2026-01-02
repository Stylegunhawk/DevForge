"""Helper tools for cheat sheet agent."""

import re
from typing import Optional

def detect_language_from_code(code: str) -> Optional[str]:
    """
    Detect programming language from code snippet using simple heuristics.
    """
    code = code.strip()
    
    # Rust (Check first to avoid 'let' confusion with TS)
    if re.search(r'\bfn\s+\w+|let\s+mut\s+|\bimpl\b|\bstruct\b|\bpub\b|println!|\bmatch\b', code):
        return "rust"

    # Go
    if re.search(r'\bfunc\s+\w+|\bpackage\b|\bimport\s*["(]|\bgo\b|\bchan\b|fmt\.|\btype\b|:=', code):
        return "go"

    # JavaScript/TypeScript (Check BEFORE Ruby to avoid false positives)
    # JavaScript has many patterns including MongoDB, Node.js, browser APIs, etc.
    js_patterns = [
        r'\bfunction\s+\w+\s*\(',      # function declaration
        r'\bconst\s+\w+\s*=',          # const declaration
        r'\blet\s+\w+\s*=',            # let declaration
        r'\bvar\s+\w+\s*=',            # var declaration
        r'console\.log\(',             # console.log
        r'\.getMongo\(',               # MongoDB: db.getMongo()
        r'\.startSession\(',           # MongoDB: session.startSession()
        r'\.startTransaction\(',       # MongoDB: session.startTransaction()
        r'\.commitTransaction\(',      # MongoDB: session.commitTransaction()
        r'\.abortTransaction\(',       # MongoDB: session.abortTransaction()
        r'\.endSession\(',             # MongoDB: session.endSession()
        r'\$inc\b',                    # MongoDB: $inc operator
        r'\$set\b',                    # MongoDB: $set operator
        r'\$push\b',                   # MongoDB: $push operator
        r'\$pull\b',                   # MongoDB: $pull operator
        r'db\.\w+',                    # MongoDB: db.collection
        r'\.find\(',                   # MongoDB: .find()
        r'\.findOne\(',                # MongoDB: .findOne()
        r'\.updateOne\(',              # MongoDB: .updateOne()
        r'\.insertOne\(',              # MongoDB: .insertOne()
        r'\.bulkWrite\(',              # MongoDB: .bulkWrite()
        r'\.readConcern\(',            # MongoDB: .readConcern()
        r'\.writeConcern\(',           # MongoDB: .writeConcern()
        r'\.session\(',                # MongoDB: .session()
        r'require\s*\(',               # Node.js: require()
        r'module\.exports',            # Node.js: module.exports
        r'\.then\s*\(',                # Promise: .then()
        r'\.catch\s*\(',               # Promise: .catch()
        r'async\s+function',           # async function
        r'await\s+',                   # await keyword
        r'\.forEach\s*\(',             # Array.forEach()
        r'\.map\s*\(',                 # Array.map()
        r'\.filter\s*\(',              # Array.filter()
    ]
    js_match = any(re.search(pattern, code) for pattern in js_patterns)
    if js_match:
        # Check for TypeScript-specific patterns
        if re.search(r':\s*\w+(\[\])?\s*[=,)]|interface\s+\w+|type\s+\w+\s*=', code):
            return "typescript"
        return "javascript"

    # Ruby (Check AFTER JavaScript to avoid false positives)
    # Ruby has distinctive syntax: puts, require, end, do...end, symbols, etc.
    # Key patterns: puts, gets, .class, .each, .map, symbols (:symbol), instance vars (@var), etc.
    ruby_patterns = [
        r'\bputs\b',           # puts statement (Ruby-specific)
        r'\bgets\b',           # gets input (Ruby-specific)
        r'\brequire\s',         # require statement (without parentheses)
        r'\.class\b',           # .class method (Ruby-specific)
        r'\.each\s*\{',         # .each { block }
        r'\.each\s+do',         # .each do block
        r'\.map\s*\{',          # .map { block }
        r'\.select\s*\{',       # .select { block }
        r'\.chomp\b',           # .chomp method (Ruby-specific)
        r'\.to_i\b',            # .to_i method (Ruby-specific)
        r'def\s+\w+\s*$',       # method definition (no parentheses, end of line)
        r'\bend\s*$',           # end keyword at end of line (but not .endSession())
        r':[\w_]+\s*[=,)]',     # symbols (:symbol)
        r'@\w+',                # instance variable (@var)
        r'@@\w+',               # class variable (@@var)
        r'\$[\w_]+',            # global variable ($var)
        r'\|\|=\s*',            # ||= operator
    ]
    # Only match Ruby if it's clearly Ruby (not JavaScript with similar patterns)
    # Check that we have Ruby-specific patterns AND not JavaScript patterns
    ruby_match = any(re.search(pattern, code) for pattern in ruby_patterns)
    if ruby_match and not js_match:
        return "ruby"

    # SQL (Check after JavaScript and Ruby to avoid false positives)
    # Only match if it looks like actual SQL (not in a string or comment)
    if re.search(r'(?i)\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|FROM|WHERE|JOIN)\b', code):
        return "sql"

    # Python
    if re.search(r'def\s+\w+\s*\(|import\s+\w+|from\s+\w+\s+import|print\(', code):
        return "python"

    # Default fallback
    return None

def format_code_block(code: str, language: str) -> str:
    """Format code into a markdown block."""
    return f"```{language}\n{code}\n```"
