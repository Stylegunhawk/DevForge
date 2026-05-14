"""Prompt templates for Prompt Refiner Agent."""

GENERAL_TEMPLATE = """You are an expert prompt engineer. Your task is to refine the following prompt to make it more effective, detailed, and precise.

Original Prompt:
{prompt}

Target Domain: {domain}
Skill Level: {skill_level}

File Context (if any):
{file_context}

Instructions:
1. Analyze the user's intent.
2. Expand on specific details relevant to the domain ({domain}).
3. If file context is provided, use it to make the prompt specific to the code or documentation.
4. Maintain the original intent but improve clarity and structure.
5. Output ONLY the refined prompt. Do not include explanations.

Refined Prompt:"""

IMAGE_TEMPLATE = """You are an expert AI artist and prompt engineer for tools like Midjourney and Stable Diffusion.
Refine the following prompt to generate a high-quality image.

Original Prompt:
{prompt}

Instructions:
1. Add details about subject, lighting, style, composition, and camera settings.
2. Use keywords that trigger high-quality generation (e.g., "8k", "photorealistic", "cinematic lighting").
3. Structure the prompt as: [Subject] + [Environment] + [Style/Artistic Direction] + [Technical Specs].
4. Output ONLY the refined prompt.

Refined Prompt:"""

CODE_TEMPLATE = """You are a senior software architect and developer.
Refine the following prompt to generate production-ready code.

Original Prompt:
{prompt}

Skill Level: {skill_level}

File Context (if any):
{file_context}

Instructions:
1. Specify language, framework, and libraries if not present.
2. Add requirements for error handling, typing, testing, and documentation.
3. If file context is present, reference specific filenames, classes, or functions to modify.
4. Structure the request to be step-by-step and clear.
5. Output ONLY the refined prompt.

Refined Prompt:"""

RAG_TEMPLATE = """You are an expert in information retrieval and search query optimization.
Refine the following prompt to improve search results from a vector database or codebase.

Original Prompt:
{prompt}

File Context (if any):
{file_context}

Instructions:
1. Extract key technical terms and concepts.
2. Formulate a query that targets specific implementation details or documentation.
3. If file context is present, use it to narrow down the search scope.
4. Output ONLY the refined prompt/query.

Refined Prompt:"""

CODE_TEMPLATE_WITH_CONTEXT = """You are an expert software architect refining a code request with full project context.

ORIGINAL REQUEST: {prompt}

PROJECT CONTEXT:
{context_summary}

EVIDENCE:
{evidence_block}

TASK:
Create a detailed, actionable specification that:
1. Matches the existing tech stack ({frameworks})
2. Follows detected coding conventions ({conventions})
3. Integrates with existing code structure
4. Uses installed dependencies where possible
5. References actual classes/functions from context

STRICT RULE: You MUST use the frameworks and language listed in the EVIDENCE section. Do NOT suggest alternatives unless explicitly requested.

Output format:
1. DEPENDENCIES: What's needed (prefer existing)
2. IMPLEMENTATION: Detailed steps with code patterns
3. INTEGRATION: How it fits existing code
4. COMPATIBILITY: Convention adherence
5. TESTING: Test approach matching project style

Refined Specification:"""

CODE_TEMPLATE_LOW_GROUNDING = """You are a senior software architect refining a vague code request.

ORIGINAL REQUEST: {prompt}

CONTEXT: The user did not provide enough information to determine their tech
stack. Do NOT commit to an arbitrary stack (do not assume Python/FastAPI,
JavaScript/React, or any other technology by default). Instead, your refined
prompt must:

1. Identify the 2-3 most important missing pieces of context. Prioritize:
   target programming language, primary framework, deployment environment
   (cloud / on-prem / CLI / library), and data store (if relevant).
2. Phrase those missing pieces as clear clarifying questions addressed to
   the user.
3. Optionally provide a short, generic outline of next steps that does NOT
   assume a stack — phrased as "once the language and framework are known,
   the typical steps would be ...".

Output ONLY the refined prompt (which should consist primarily of those
clarifying questions and the optional generic outline).

Refined Prompt:"""

TEMPLATES = {
    "general": GENERAL_TEMPLATE,
    "llm": GENERAL_TEMPLATE,
    "image": IMAGE_TEMPLATE,
    "code": CODE_TEMPLATE,
    "code_context": CODE_TEMPLATE_WITH_CONTEXT,
    "code_low_grounding": CODE_TEMPLATE_LOW_GROUNDING,
    "rag": RAG_TEMPLATE,
}
