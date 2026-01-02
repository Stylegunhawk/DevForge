"""Templates for cheat sheet generation."""

CHEATSHEET_TEMPLATE = """# {{ language }} Cheat Sheet - {{ skill_level|title }}

{% for section in sections %}
## {{ loop.index }}. {{ section.title }}
{{ section.content }}

{% endfor %}

## Quick Reference
| Task | Code |
|------|------|
{% for ref in quick_refs %}
| {{ ref.task }} | `{{ ref.code }}` |
{% endfor %}
"""

SECTION_TEMPLATE = """
{{ content }}
"""
