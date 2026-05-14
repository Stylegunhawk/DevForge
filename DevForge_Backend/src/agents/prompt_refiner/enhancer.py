"""Prompt enhancement logic using LLM."""

import logging
from typing import Optional, Dict, Any, List
from src.agents.prompt_refiner.templates import TEMPLATES
from src.core.model_router import model_router
from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
from src.agents.prompt_refiner.sanitizer import Sanitizer
from src.agents.prompt_refiner.conversation_parser import ConversationParser
from src.agents.prompt_refiner.context_types import CodeContext, ChosenStack, Evidence

logger = logging.getLogger(__name__)


# Framework name normalization map
FRAMEWORK_NORMALIZED_MAP = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "react": "React",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "express": "Express.js",
    "express.js": "Express.js",
    "next": "Next.js",
    "next.js": "Next.js",
}


class PromptEnhancer:
    """Enhances prompts using LLM and domain-specific templates."""

    def __init__(self):
        """Initialize the enhancer."""
        self.dependency_analyzer = DependencyAnalyzer()
        self.sanitizer = Sanitizer()

    async def enhance(
        self,
        prompt: str,
        domain: str = "general",
        skill_level: str = "intermediate",
        file_context: Optional[str] = None,
        code_context: Optional['CodeContext'] = None,
        project_files: Optional[Dict[str, str]] = None,
        tenant_id: Optional[str] = None,
        integration_name: Optional[str] = None,
        user_id: Optional[str] = None  # NEW: Phase 4 analytics support
    ) -> Dict[str, Any]:
        """Enhance a prompt based on domain and context.

        Args:
            prompt: Original user prompt.
            domain: Target domain (image, code, rag, llm).
            skill_level: User skill level.
            file_context: Optional context from files.
            code_context: Optional code context.
            project_files: Optional project files for dependency analysis.

        Returns:
            Dictionary with refined_prompt, context_summary, chosen_stack, sanitization_log
        """
        try:
            # 1. Sanitize Inputs
            safe_prompt, sanitization_log = self.sanitizer.sanitize(prompt)
            safe_file_context = None
            if file_context:
                safe_file_context, file_log = self.sanitizer.sanitize(file_context)
                sanitization_log.extend(file_log)

            # 2. Gather Evidence
            all_evidence: List[Evidence] = []
            
            # Dependency evidence (highest weight)
            if project_files:
                dep_evidence = self.dependency_analyzer.analyze(project_files)
                all_evidence.extend(dep_evidence)
            
            # Code structure evidence (medium weight)
            if code_context and code_context.code_structure.imports:
                code_evidence = self._extract_code_evidence(code_context)
                all_evidence.extend(code_evidence)
            
            # Conversation evidence (lowest weight)
            if code_context and code_context.conversation.technologies:
                conv_evidence = self._extract_conversation_evidence(code_context)
                all_evidence.extend(conv_evidence)

            # 3. Build ChosenStack with deterministic confidence
            chosen_stack = self._build_chosen_stack(all_evidence)

            # 4. Compute deterministic quality block (no LLM call)
            quality = self._compute_quality(prompt, code_context, chosen_stack)

            # 5. Format context summary and evidence block
            context_summary = self._format_context_summary(code_context, chosen_stack)
            evidence_block = self._format_evidence_block(all_evidence)

            # Select appropriate template.
            #   - confidence >= 0.6     → strict EVIDENCE-bound template
            #   - low grounding + code  → soft clarifying-questions template
            #   - otherwise             → default per-domain template
            template_key = domain
            if domain == "code":
                if chosen_stack.confidence >= 0.6:
                    template_key = "code_context"
                elif quality["prompt_grounding"] == "low":
                    template_key = "code_low_grounding"
            
            template = TEMPLATES.get(template_key, TEMPLATES["general"])

            # Prepare format arguments
            format_args = {
                "prompt": safe_prompt,
                "domain": domain,
                "skill_level": skill_level,
                "file_context": safe_file_context or "None",
            }
            
            # Add context arguments if using context template
            if template_key == "code_context":
                format_args["context_summary"] = context_summary
                format_args["evidence_block"] = evidence_block
                format_args["frameworks"] = ", ".join(chosen_stack.frameworks) if chosen_stack.frameworks else "None detected"
                format_args["conventions"] = str(code_context.code_structure.conventions) if code_context else "{}"

            # Format the prompt
            formatted_prompt = template.format(**format_args)

            # Select model for refinement
            model_name = model_router.select_model_by_task("routing")
            chat_model = model_router.get_chat_model(model_name)

            logger.info(
                f"Enhancing prompt for domain '{domain}' using model '{model_name}'",
                extra={
                    "original_length": len(prompt),
                    "evidence_count": len(all_evidence),
                    "confidence": chosen_stack.confidence
                },
            )

            # Phase 2: Use ModelRouter.invoke_with_usage for token tracking
            usage_result = await model_router.invoke_with_usage(
                prompt=formatted_prompt,
                model_name=model_name,
                tenant_id=tenant_id,
                integration_name=integration_name,
                task_type=f"prompt_refiner_{domain}",
                user_id=user_id  # NEW: Pass user_id to ModelRouter
            )
            
            refined_prompt = usage_result.content.strip()

            logger.info(
                "Prompt enhanced successfully",
                extra={"refined_length": len(refined_prompt)},
            )

            return {
                "refined_prompt": refined_prompt,
                "context_summary": context_summary,
                "chosen_stack": chosen_stack.to_dict(),
                "sanitization_log": sanitization_log,
                "quality": quality,
            }

        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}", exc_info=True)
            # Fallback: return original prompt with empty stack
            return {
                "refined_prompt": prompt,
                "context_summary": "Error during enhancement",
                "chosen_stack": ChosenStack().to_dict(),
                "sanitization_log": [],
                "quality": {
                    "prompt_grounding": "low",
                    "missing_signals": ["language", "framework", "database", "specificity"],
                    "suggested_inputs": ["attached_files", "conversation_history", "project_files"],
                },
                "error": str(e),
            }

    # Frameworks detectable from code imports. Kept aligned with
    # DependencyAnalyzer.PACKAGE_MAP so coverage is symmetric between
    # dependency files and attached source code.
    _CODE_FRAMEWORK_CHECKS = [
        ("fastapi", "FastAPI", 0.8),
        ("flask", "Flask", 0.8),
        ("django", "Django", 0.8),
        ("sqlalchemy", "SQLAlchemy", 0.6),
        ("react", "React", 0.8),
        ("vue", "Vue.js", 0.8),
        ("next", "Next.js", 0.8),
        ("express", "Express.js", 0.8),
        ("angular", "Angular", 0.8),
    ]

    def _extract_code_evidence(self, context: CodeContext) -> List[Evidence]:
        """Extract evidence from code structure."""
        evidence = []
        imports_text = " ".join(context.code_structure.imports).lower()

        # SQLAlchemy is the only library in this list; everything else is a
        # web/app framework. Map by name rather than maintaining a parallel
        # list, to keep this in sync if more libs get added later.
        library_names = {"SQLAlchemy"}

        for keyword, framework, weight in self._CODE_FRAMEWORK_CHECKS:
            if keyword in imports_text:
                # Find the import line
                for idx, imp in enumerate(context.code_structure.imports):
                    if keyword in imp.lower():
                        evidence.append(Evidence(
                            source="code_analysis",
                            file="<attached_code>",
                            line=idx + 1,
                            excerpt=imp[:50],
                            match=framework,
                            weight=weight,
                            confidence_hint="strong",
                            category="library" if framework in library_names else "framework",
                        ))
                        break

        return evidence

    # Maps normalized display names to their primary language. Built once
    # from PACKAGE_MAP so adding a new ecosystem in dependency_analyzer.py
    # automatically extends language detection here too. Conversation-only
    # tech names (AWS, PostgreSQL, etc.) are layered on after.
    @staticmethod
    def _build_name_to_language_map() -> Dict[str, str]:
        from src.agents.prompt_refiner.dependency_analyzer import PACKAGE_MAP
        m: Dict[str, str] = {}
        for info in PACKAGE_MAP.values():
            m[str(info["name"])] = str(info["language"])
        # Code-evidence framework names that aren't in PACKAGE_MAP
        # (covered by _CODE_FRAMEWORK_CHECKS only).
        m.setdefault("FastAPI", "python")
        m.setdefault("Django", "python")
        m.setdefault("Flask", "python")
        m.setdefault("SQLAlchemy", "python")
        m.setdefault("React", "javascript")
        m.setdefault("Vue.js", "javascript")
        m.setdefault("Next.js", "javascript")
        m.setdefault("Express.js", "javascript")
        m.setdefault("Angular", "javascript")
        m.setdefault("TypeScript", "typescript")
        return m

    _NAME_TO_LANGUAGE: Dict[str, str] = {}  # populated lazily

    @classmethod
    def _name_to_language(cls) -> Dict[str, str]:
        if not cls._NAME_TO_LANGUAGE:
            cls._NAME_TO_LANGUAGE = cls._build_name_to_language_map()
        return cls._NAME_TO_LANGUAGE

    def _pick_primary_language(self, all_evidence: List[Evidence]) -> str:
        """Pick the language carrying the highest-weighted evidence.

        Ties resolve alphabetically for stable output. Languages explicitly
        present as `category == "language"` evidence (e.g. TypeScript)
        also count toward the score.
        """
        name_to_lang = self._name_to_language()
        scores: Dict[str, float] = {}
        for ev in all_evidence:
            lang = name_to_lang.get(ev.match)
            if not lang or lang == "unknown":
                continue
            scores[lang] = max(scores.get(lang, 0.0), ev.weight)
        if not scores:
            return "unknown"
        # Sort by (-weight, name) so highest weight wins; alphabetical tie-break.
        return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _compute_quality(
        self,
        prompt: str,
        code_context: Optional[CodeContext],
        chosen_stack: ChosenStack,
    ) -> Dict[str, Any]:
        """Compute a deterministic quality block for the response.

        Pure function — no LLM call, no randomness, no I/O. Tells the
        calling agent how well-grounded the refined prompt is and which
        input fields would most improve a follow-up call.

        Returns a dict with three keys:
            prompt_grounding: "low" | "medium" | "high"
            missing_signals:  subset of [language, framework, database, specificity]
            suggested_inputs: subset of [project_files, attached_files,
                                         conversation_history, file_context]
        """
        tokens = len((prompt or "").split())
        confidence = chosen_stack.confidence

        if tokens >= 8 and confidence >= 0.7:
            grounding = "high"
        elif tokens >= 5 or confidence >= 0.4:
            grounding = "medium"
        else:
            grounding = "low"

        missing: List[str] = []
        if not chosen_stack.languages:
            missing.append("language")
        if not chosen_stack.frameworks:
            missing.append("framework")
        if not chosen_stack.databases:
            missing.append("database")
        if tokens < 5:
            missing.append("specificity")

        suggested: set = set()
        if "framework" in missing or "language" in missing:
            suggested.add("project_files")
        has_code = bool(
            code_context
            and code_context.code_structure
            and code_context.code_structure.imports
        )
        if not has_code:
            suggested.add("attached_files")
        if grounding == "low":
            suggested.add("conversation_history")

        return {
            "prompt_grounding": grounding,
            "missing_signals": missing,
            "suggested_inputs": sorted(suggested),
        }

    def _extract_conversation_evidence(self, context: CodeContext) -> List[Evidence]:
        """Extract evidence from conversation.

        Categorizes each detected technology via ConversationParser.CATEGORY_MAP:
        databases like PostgreSQL go to "database", cloud / infra like AWS go to
        "service", language names like TypeScript go to "language", and anything
        not explicitly mapped falls back to "framework" (matching v0.9 behavior
        for unmapped names).
        """
        evidence = []
        category_map = ConversationParser.CATEGORY_MAP

        for tech in context.conversation.technologies:
            normalized = FRAMEWORK_NORMALIZED_MAP.get(tech.lower(), tech)
            category = category_map.get(normalized, "framework")
            evidence.append(Evidence(
                source="conversation",
                match=normalized,
                weight=0.4,  # Low weight for conversation
                confidence_hint="weak",
                category=category,
            ))

        return evidence

    def _build_chosen_stack(self, all_evidence: List[Evidence]) -> ChosenStack:
        """Build chosen stack with deterministic confidence calculation.
        
        Multi-Stack Policy:
        - ALL frameworks with evidence are included in the frameworks list
        - Frameworks are sorted alphabetically for deterministic output
        - Each framework retains its evidence for traceability
        - Confidence is computed from top 3 evidence items (any framework)
        - Primary source is determined by highest-weighted single evidence
        
        Example: If evidence contains FastAPI (0.9) + React (0.8) + Django (0.4),
        all three will be in frameworks list, but source='dependency_analysis'
        (from FastAPI) and confidence=0.87 (avg of top 3).
        
        Confidence formula:
        - Average of top 3 evidence weights (regardless of framework)
        - Capped at 1.0
        """
        if not all_evidence:
            return ChosenStack()
        
        # Group evidence by framework
        framework_evidence = {}
        language_evidence = {}
        
        for ev in all_evidence:
            match = ev.match
            # Normalize framework name
            normalized = FRAMEWORK_NORMALIZED_MAP.get(match.lower(), match)
            
            if normalized not in framework_evidence:
                framework_evidence[normalized] = []
            framework_evidence[normalized].append(ev)
        
        # Compute aggregated confidence per framework
        framework_scores = {}
        for framework, evidences in framework_evidence.items():
            total_weight = sum(e.weight for e in evidences)
            framework_scores[framework] = total_weight
        
        # Determine primary source (highest weighted evidence)
        primary_source = "none"
        if all_evidence:
            sorted_evidence = sorted(all_evidence, key=lambda e: e.weight, reverse=True)
            primary_source = sorted_evidence[0].source
        
        # Overall confidence: average of top evidence weights
        top_weights = sorted([e.weight for e in all_evidence], reverse=True)[:3]
        confidence = sum(top_weights) / len(top_weights) if top_weights else 0.0
        confidence = min(confidence, 1.0)  # Cap at 1.0
        
        # Determine primary language from evidence. Multiple language
        # ecosystems may coexist (e.g. Python backend + JS frontend, or a
        # polyglot monorepo). Pick the language carrying the
        # highest-weighted evidence; ties resolve via deterministic
        # alphabetical order so the result is stable across calls.
        language = self._pick_primary_language(all_evidence)
        
        # Route evidence into category-typed lists. Each list is a sorted,
        # deduplicated set of normalized names.
        def _by_category(cat: str) -> List[str]:
            return sorted({
                FRAMEWORK_NORMALIZED_MAP.get(e.match.lower(), e.match)
                for e in all_evidence
                if e.category == cat
            })

        languages = _by_category("language")
        frameworks_list = _by_category("framework")
        libraries = _by_category("library")
        services = _by_category("service")
        databases = _by_category("database")

        # `frameworks` is now the framework-only filtered view (denormalized
        # so v0.9 callers reading chosen_stack.frameworks keep working — but
        # without services like AWS/Redis polluting it).
        # Primary `database` field: pick the first database for back-compat;
        # full list lives in `databases`.
        primary_db = databases[0] if databases else "unknown"

        return ChosenStack(
            language=language,
            frameworks=frameworks_list,
            database=primary_db,
            source=primary_source,
            confidence=confidence,
            evidence=all_evidence,
            languages=languages,
            libraries=libraries,
            services=services,
            databases=databases,
        )

    def _format_context_summary(self, context: Optional[CodeContext], stack: ChosenStack) -> str:
        """Format context summary for LLM."""
        if not context:
            return "No context available"
        
        lines = []
        if stack.language != "unknown":
            lines.append(f"- Language: {stack.language}")
        if stack.frameworks:
            lines.append(f"- Frameworks: {', '.join(stack.frameworks)}")
        if context.code_structure.classes:
            lines.append(f"- Existing Classes: {', '.join(context.code_structure.classes)}")
        if context.code_structure.functions:
            lines.append(f"- Existing Functions: {', '.join(context.code_structure.functions)}")
        if context.recent_context:
            lines.append(f"- Recent Work: {context.recent_context}")
        
        return "\n".join(lines) if lines else "Minimal context"

    def _format_evidence_block(self, evidence_list: List[Evidence]) -> str:
        """Format evidence block for LLM prompt."""
        if not evidence_list:
            return "No evidence available"
        
        lines = []
        for ev in sorted(evidence_list, key=lambda e: e.weight, reverse=True):
            source_str = ev.source.replace("_", " ").title()
            file_str = f" ({ev.file}:{ev.line})" if ev.file and ev.line else ""
            lines.append(f"- {ev.match} (source: {source_str}{file_str}, weight: {ev.weight:.1f})")
        
        return "\n".join(lines)
