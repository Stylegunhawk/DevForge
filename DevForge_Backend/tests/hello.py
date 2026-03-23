# Integer caching
a = 256
b = 256
print(a is b)  # True  (cached)

a = 257
b = 257
print(a is b)  # False (not cached) - implementation dependent!

# String interning
a = "hello"
b = "hello"
print(a is b)  # True  (interned - simple identifier-like strings)

a = "hello world"  # contains space
b = "hello world"
print(a is b)  # May be False!

import sys
a = sys.intern("my string")  # force interning
b = sys.intern("my string")
print(a is b)  # True