"""Generate skill-appropriate quick reference tables"""

from typing import List, Tuple


def generate_quick_reference(
    language: str,
    skill_level: str,
    detected_libraries: List[str]
) -> str:
    """
    Generate markdown quick reference table.
    
    Args:
        language: Programming language
        skill_level: 'beginner', 'intermediate', or 'expert'
        detected_libraries: List of detected library names
        
    Returns:
        Markdown formatted quick reference table
    """
    if skill_level == 'beginner':
        return _beginner_quick_ref(language)
    elif skill_level == 'intermediate':
        return _intermediate_quick_ref(language, detected_libraries)
    else:
        return _expert_quick_ref(language, detected_libraries)


def _beginner_quick_ref(language: str) -> str:
    """Essential operations for beginners"""
    refs = [
        ('Print to console', 'print(value)'),
        ('Define variable', 'name = value'),
        ('Define function', 'def name(args):'),
        ('If statement', 'if condition:'),
        ('For loop', 'for x in items:'),
        ('Import module', 'import module'),
    ]
    return _build_table(refs, columns=['Task', 'Code'])


def _intermediate_quick_ref(language: str, libs: List[str]) -> str:
    """Patterns + library-specific shortcuts"""
    refs = []
    
    # Add library-specific
    if 'pandas' in libs:
        refs.extend([
            ('Load CSV', 'pd.read_csv("file.csv")', 'DataFrame I/O'),
            ('Filter rows', 'df[df["col"] > 10]', 'Boolean indexing'),
            ('Group & aggregate', 'df.groupby("col").mean()', 'Summarize data'),
        ])
    
    if 'fastapi' in libs:
        refs.extend([
            ('GET route', '@app.get("/path")', 'Read endpoint'),
            ('POST with body', '@app.post("/path")', 'Create endpoint'),
            ('Dependency injection', 'Depends(func)', 'Share resources'),
        ])
    
    # Add general patterns
    refs.extend([
        ('List comprehension', '[x*2 for x in items]', 'Transform lists'),
        ('Dict comprehension', '{k: v*2 for k, v in d.items()}', 'Transform dicts'),
        ('Lambda function', 'lambda x: x*2', 'Anonymous function'),
    ])
    
    return _build_table(refs, columns=['Pattern', 'Code', 'Use Case'])


def _expert_quick_ref(language: str, libs: List[str]) -> str:
    """Advanced techniques and optimizations"""
    refs = [
        ('Generator expression', '(x for x in range(10**6))', 'Memory efficient iteration'),
        ('Decorator', '@decorator', 'Modify function behavior'),
        ('Context manager', 'with resource as r:', 'Auto cleanup'),
        ('__slots__', 'class C: __slots__ = ["x"]', '40% faster attribute access'),
    ]
    
    if 'asyncio' in libs:
        refs.extend([
            ('Concurrent tasks', 'await asyncio.gather(*tasks)', 'Run in parallel'),
            ('Task creation', 'asyncio.create_task(coro)', 'Background execution'),
        ])
    
    return _build_table(refs, columns=['Technique', 'Code', 'Benefit'])


def _build_table(refs: List[Tuple], columns: List[str]) -> str:
    """Build markdown table from references"""
    # Header
    header = '| ' + ' | '.join(columns) + ' |'
    separator = '|' + '|'.join(['---'] * len(columns)) + '|'
    
    # Rows
    rows = []
    for ref in refs:
        # Format code column with backticks (usually column index 1)
        formatted_ref = list(ref)
        if len(formatted_ref) > 1:
            formatted_ref[1] = f'`{formatted_ref[1]}`'
        row = '| ' + ' | '.join(formatted_ref) + ' |'
        rows.append(row)
    
    return '\n'.join(['\n## Quick Reference\n', header, separator] + rows)
