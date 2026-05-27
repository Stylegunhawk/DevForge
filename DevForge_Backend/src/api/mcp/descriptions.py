"""Agent-instructive tool descriptions surfaced via MCP `tools/list`.

These long strings teach calling agents the iterative call pattern,
cache-latency expectations, and per-parameter usage. They must be preserved
verbatim — drift here regresses tool-calling quality for downstream agents.

Source of truth was previously src/api/routers/__init__.py:178-286.
"""

TOOL_DESCRIPTIONS: dict[str, str] = {
    "generate_data": (
        "Synthetic data generator with three modes: "

        "V1 (Faker, fast): no prompt, no domain — returns CSV/JSON Faker rows in "
        "under 1s. Use for quick mock users in unit tests. "

        "V2 DOMAIN TEMPLATE: domain='ecommerce'|'saas'|'iot_devices' — pre-built "
        "multi-entity schema with FK integrity (no schema-design LLM call). "
        "~5-10s warm-cache / 15-25s cold-cache. Use for realistic ecommerce / saas / "
        "iot-devices data with valid foreign-key linkage. "

        "V2 PROMPT MODE: prompt='...' — LLM designs the schema, SchemaValidator "
        "fixes enum-swap + range inference, per-entity LLM catalog generates "
        "domain-realistic values for every string field (cached L1/L2 with 1h TTL). "
        "~15-30s cold-cache / ~5-10s warm. Use for novel domains the templates "
        "don't cover (e.g. 'vintage motorcycles', 'scientific instruments'). "
        "Pass the user's prompt verbatim. "

        "ARGS: rows (1-10000), format ('json'|'csv'), realism_level "
        "('basic'|'medium'|'high'). realism_level='high' injects ~10% nulls into "
        "nullable business fields (phone, address, last_login, description, "
        "cancellation_reason, error_message, last_seen, error_code) and ~2% "
        "duplicates / ~1% outliers; critical fields (id, email, created_at, "
        "uuid, *_id foreign keys) NEVER get nulls. Default 'basic' = no injection. "

        "OUTPUT: data.entities (entity names), data.data (per-entity row arrays "
        "for JSON or CSV strings for CSV), data.fk_integrity (per-relationship "
        "orphan counts), data.constraint_violations (empty on success), "
        "data._internal_success (boolean). Constraint violations clear data "
        "and set success=false."
    ),
    "github_operation": (
        "Unified GitHub automation tool: 26 structured ops + NL routing for "
        "repo management, branch lifecycle, issues, PRs, commits, releases, Actions, and webhooks. "
        "TWO CALL MODES — use structured when the op is known (1-2s faster, no LLM classification): "
        "  Structured: {operation, repo_name, <op params>, context:{github_token}} "
        "  Natural-language: {query, context:{github_token}} "
        "LOW risk ops (no confirmation): browse_files, read_file, list_repos, list_branches, "
        "search_code, list_pull_requests, get_pr, list_commits, get_commit, "
        "list_releases, list_webhooks, add_comment. "
        "MEDIUM ops (no confirmation): create_issue, commit_file, create_branch, "
        "create_pull_request, merge_pr, close_issue, update_issue. "
        "HIGH ops (context.risk_confirmed=true required): create_repo, delete_branch, "
        "create_release, trigger_workflow, create_webhook, delete_webhook. "
        "CRITICAL ops (risk_confirmed=true + risk_reason required): delete_repo. "
        "CONTEXTUAL ESCALATION: "
        "merge_pr base=main/master → HIGH; base=production/release/* → CRITICAL. "
        "delete_branch branch_name=main/master/production → CRITICAL. "
        "commit_file branch=main/master/production → HIGH. "
        "create_release prerelease=True → MEDIUM (no confirmation needed). "
        "NL-only ops (LLM-routed): generate_changelog, analyze_ci_failure, scaffold_repo. "
        "READ FILE: pass branch='<ref>' to read from non-default branch. "
        "FILE COMMITS: system auto-injects file_url from context.available_files. "
        "GITOPS_PROTECTED_MODE=true blocks all HIGH/CRITICAL ops."
    ),
    "refine_prompt": (
        "Refines a user prompt into a detailed, production-ready specification, "
        "with optional tech-stack grounding from project files, conversation "
        "history, or attached code. "

        "ITERATIVE USE (recommended for agents): Call once with the user's raw "
        "prompt. The response's `quality.prompt_grounding` field returns 'low', "
        "'medium', or 'high'. If 'low' or 'medium', re-call with the inputs "
        "named in `quality.suggested_inputs` (e.g. project_files, "
        "attached_files, conversation_history). Each enrichment cycle improves "
        "the refined prompt's grounding. "

        "OUTPUT: data.refined_prompt is the refined prompt text. "
        "data.chosen_stack splits detected tech into languages, frameworks, "
        "libraries, services, and databases — use these typed lists, not the "
        "legacy denormalized `frameworks` field. "
        "data.sanitization_log lists redacted secrets and blocked prompt "
        "injection attempts (metadata only — actual secrets are never logged). "

        "SUPPORTED MANIFEST FILES for project_files: requirements.txt, "
        "package.json, go.mod, Cargo.toml, pom.xml, build.gradle, "
        "build.gradle.kts, Gemfile, composer.json, *.csproj. "

        "DOMAINS: code, image, rag, llm, general (default)."
    ),
    "generate_cheatsheet": (
        "Generates an activity-aware programming cheat sheet from curated, "
        "human-reviewed knowledge packs (one LLM call for personalization). "

        "SUPPORTED LANGUAGES: python, javascript, typescript, go, rust, java, "
        "ruby, php, csharp. Unsupported languages return success:false with a "
        "clear message — DO NOT retry with a different value, ask the user. "

        "INPUTS you should provide: "
        "  - language (one of the above, or omit to auto-detect from code_context) "
        "  - skill_level (beginner|intermediate|expert; default beginner) "
        "  - code_context (paste the user's actual code if available — enables "
        "    library detection and activity-aware ranking) "
        "  - intent (1-line description of what the user is trying to do, e.g. "
        "    'debugging async deadlock' — strongly improves relevance when code "
        "    is unavailable or short). "

        "OUTPUTS: data.markdown (rendered sheet), data.ranked_entries (structured), "
        "data.packs_used (provenance for citing), data.quality ('curated' = LLM-"
        "personalized; 'curated_unpersonalized' = deterministic fallback fired "
        "because LLM returned bad JSON — content is still trustworthy but not "
        "tailored), data.detected_libraries, data.complexity_score, "
        "data.complexity_suggested_level. "

        "LATENCY: 5–15s warm-cache, 20–30s cold-cache (free Ollama). Suggest a "
        "loading indicator to the user."
    ),
}
