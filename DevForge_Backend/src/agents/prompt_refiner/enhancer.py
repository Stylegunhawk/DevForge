"""Prompt enhancement logic using LLM."""

import logging
from typing import Optional, Dict, Any, List
from src.agents.prompt_refiner.templates import TEMPLATES
from src.core.model_router import model_router
from src.agents.prompt_refiner.dependency_analyzer import DependencyAnalyzer
from src.agents.prompt_refiner.sanitizer import Sanitizer
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
        integration_name: Optional[str] = None
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

            # 4. Format context summary and evidence block
            context_summary = self._format_context_summary(code_context, chosen_stack)
            evidence_block = self._format_evidence_block(all_evidence)

            # Select appropriate template
            template_key = domain
            if domain == "code" and chosen_stack.confidence > 0.0:
                template_key = "code_context"
            
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
                task_type=f"prompt_refiner_{domain}"
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
                "sanitization_log": sanitization_log
            }

        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}", exc_info=True)
            # Fallback: return original prompt with empty stack
            return {
                "refined_prompt": prompt,
                "context_summary": "Error during enhancement",
                "chosen_stack": ChosenStack().to_dict(),
                "sanitization_log": [],
                "error": str(e)
            }

    def _extract_code_evidence(self, context: CodeContext) -> List[Evidence]:
        """Extract evidence from code structure."""
        evidence = []
        imports_text = " ".join(context.code_structure.imports).lower()
        
        # Check for framework mentions in imports
        framework_checks = [
            ("fastapi", "FastAPI", 0.8),
            ("flask", "Flask", 0.8),
            ("django", "Django", 0.8),
            ("react", "React", 0.8),
        ]
        
        for keyword, framework, weight in framework_checks:
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
                            confidence_hint="strong"
                        ))
                        break
        
        return evidence

    def _extract_conversation_evidence(self, context: CodeContext) -> List[Evidence]:
        """Extract evidence from conversation."""
        evidence = []
        
        for tech in context.conversation.technologies:
            normalized = FRAMEWORK_NORMALIZED_MAP.get(tech.lower(), tech)
            evidence.append(Evidence(
                source="conversation",
                match=normalized,
                weight=0.4,  # Low weight for conversation
                confidence_hint="weak"
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
        
        # Determine language from evidence
        language = "unknown"
        for ev in all_evidence:
            if ev.source == "dependency_analysis" and "Python" in ev.match or "FastAPI" in ev.match or "Django" in ev.match or "Flask" in ev.match:
                language = "python"
                break
            if "React" in ev.match or "Vue" in ev.match or "Angular" in ev.match:
                language = "javascript" if language == "unknown" else language
        
        return ChosenStack(
            language=language,
            frameworks=sorted(list(framework_scores.keys())),
            database="unknown",
            source=primary_source,
            confidence=confidence,
            evidence=all_evidence
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
