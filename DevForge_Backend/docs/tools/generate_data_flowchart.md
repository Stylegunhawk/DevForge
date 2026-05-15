@startuml
title generate_data v0.9 Pipeline (Catalog-Sandbox + Realism Consolidation)

start
:Receive Request (Arguments);

partition "Input Validation (Pydantic gate)" {
    :Validate Rows (1-10000);
    :Validate Format (json/csv);

    if (V2 Mode?) then (Yes)
        :Validate Realism (basic/medium/high);
        :Validate Domain (if provided);
    endif

    if (Validation Failed?) then (Yes)
        :Return <b>JSON-RPC error -32603</b>
        With validation message;
        stop
    endif
}

if (Prompt or Domain provided?) then (Yes)
    :<b>V2 Mode (Advanced)</b>;

    if (ENABLE_SEMANTIC_ANALYZER\nAND enable_semantic_generation?) then (Yes)
        :Initialize Semantic Components
        (CatalogFactory, SemanticAnalyzer,
        SemanticRouter);
        note right
          <b>Two-Tier Caching</b>
          L1: Request Scope
          L2: Process Scope (1h TTL)
          Key: entity_catalog:{entity}:
            {fields_hash}:{prompt_hash}
        end note
        :Set semantic_generation_used = True;
    else (No)
        :Initialize Basic Generator (Faker-only);
        :Set semantic_generation_used = False;
    endif

    partition "Step 1: Schema Design (LLM call #1)" {
        if (Prompt provided?) then (Yes)
            :LLM Schema Design
            (Natural Language -> SchemaDesign)
            via schema_designer.design_schema();
            note right
              v0.9 prompt update:
              explicit nullable rules
              + few-shot examples
            end note
        else (No)
            :Load Domain Template
            (ecommerce / saas / iot_devices);
        endif
    }

    partition "Step 2: SchemaValidator (v0.9, pure function)" {
        :Match `<field> enum: [...]` patterns
        in user prompt;
        if (Prompt enum found?) then (Yes)
            :Force values onto named field;
            :Clear same values from
             any other field (swap fix);
        endif
        :Walk numeric fields without min/max;
        :Apply RANGE_HINTS by field-name
         (longest-match wins);
        note right
          Examples:
          bedroom_count -> (1,6)
          age -> (1,120)
          year_built -> (1900,2030)
          square_feet -> (200,20000)
        end note
    }

    partition "Step 3: Semantic Analysis (5-Tier)" {
        :Analyze Schema Fields;
        partition "Waterfall Pipeline" {
            :1. Lexical (dictionary match);
            if (found?) then (No)
                :2. Pattern (regex);
                if (found?) then (No)
                    :3. Context (heuristic);
                    if (found?) then (No)
                        :4. LLM Classification;
                        note right
                          <b>Metadata Only</b>
                          Returns semantic_type,
                          never values
                        end note
                        if (found?) then (No)
                            :5. Fallback (UNKNOWN/FREE_TEXT);
                        endif
                    endif
                endif
            endif
        }
        :Return Semantic Metadata
        per field;
    }

    partition "Step 4: Catalog-Sandbox Precompute (v0.9, LLM call per entity)" {
        :For each entity:;
        if (Cache hit on L1?) then (Yes)
            :Return cached catalog;
        elseif (Cache hit on L2?) then (Yes)
            :Promote to L1 and return;
        else (No - cold cache)
            :LLM call: get_entity_catalogs(
              entity, fields, prompt, count=50);
            note right
              Single LLM call per entity
              returns {field: [50 values]}
              Tracked via:
              model_router.invoke_with_usage(
                task_type=
                "datagen_catalog_generation")
            end note
            if (LLM succeeded & >=40 values/field?) then (Yes)
                :Cache catalog (L1 + L2);
            else (No)
                :Per-field fallback:
                _smart_field_fallback()
                (catch_phrase for _name,
                short sentence for description,
                faker.word() default);
            endif
        endif
        :Store self._entity_catalogs[entity];
    }

    partition "Step 5: Generator Selection & Execution" {
        if (Relationships exist?) then (Yes)
            :Init RelationshipEngine;
            note right
              FK linkage enforced
              during generation
              (no longer "tracking only")
            end note
            :Build SemanticFieldGeneratorAdapter
            (router + semantic_info + catalogs);
        else (No)
            :Init Independent Generator;
        endif

        :Loop through Entities;
        :Loop through Rows;

        partition "Step 6: Per-row Value Production" {
            :Lookup semantic_type
            + field_catalog for this field;

            :Constraint precedence check:;
            if (Has Enum?) then (Yes)
                :Random choice from enum;
            elseif (Has Pattern?) then (Yes)
                :rstr.xeger(pattern);
            elseif (Has field_catalog
                   AND semantic_type in
                   {free_text, unknown,
                    enum_value-no-values}?) then (Yes)
                :random.choice(field_catalog);
                note right
                  <b>v0.9 catalog-sandbox</b>
                  Domain-realistic values
                  (Spectrophotometer, Pascal,
                  Bimota S4, Mojito, etc.)
                end note
            elseif (Known semantic type?) then (Yes)
                :Dedicated generator
                (faker.email/zipcode/etc
                or curated catalog);
            else (Default)
                :_smart_free_text fallback
                (catch_phrase / sentence /
                numeric range / word);
            endif

            :Generate Value;
        }

        :Row Complete;
        :Entity Complete;
    }

    partition "Step 7: Validation & Safety (Invariant 3)" {
        :Validate Constraints
        (pattern / enum / min-max / nullable);

        :Validate Foreign Key Integrity;
        :Build FK Integrity Statistics
        (total_children, orphaned_children,
         parents_with_children, ...);

        if (Violations Found?) then (Yes)
            :Build constraint_violations array;
            :<b>Clear Data</b>
            (Invariant 3: no invalid data returned);
            :Set _internal_success = False;
        else (No - success)
            :Set _internal_success = True;
        endif
    }

    partition "Step 8: Realism (v0.9 consolidated)" {
        if (realism_level != basic?) then (Yes)
            :Single call:
            realism_engine.apply_realism_to_data(
              data, schema_design, level);
            note right
              <b>v0.9: consolidated</b>
              V2 internal _apply_realism deleted
              (was applying realism twice + only nulls).
              Now routes through realism_engine:
              - nulls (medium 5% / high 10%)
              - duplicates (high 2%)
              - outliers (high 1%)
              Respects critical-field protection:
              email/phone/uuid/id/created_at
              NEVER null.
            end note
        else (No)
            :Skip realism;
        endif
    }

    partition "Step 9: Observability" {
        :Capture Performance Metrics
        (analysis_ms, generation_ms, total_ms);
        :Build Metadata
        (source counts, confidence, warnings);
        :Attach _internal_success flag;
    }

else (No)
    :<b>V1 Mode (Faker-only, fast path)</b>;
    :Determine Fields (Custom vs Default);
    :Loop Rows (1 to N);
    :Generate Mock Data (Faker);
    :Format Output (JSON/CSV);
    :Set Internal Success = True;
endif

partition "Output Formatting" {
    :Format Response (JSON/CSV);
    if (Internal Success?) then (True)
        :Return <b>Success: True</b>
        With Data + Metadata;
    else (False)
        :Return <b>Success: False</b>
        With Empty Data + Violations;
        note right
          <b>Invariant 8</b>
          Deterministic Success.
          Fail-closed at three layers
          (v0.8.5 silent-success bug fixed):
          1. Generator: success=False if NameError
          2. Wrapper: success-calc checks
             metadata.error
          3. Agent: _internal_success default=False
        end note
    endif
}

partition "Analytics (Dashboard /usage/ page)" {
    :Async log via Celery:
    log_request_call.delay(
      user_id, tenant_id, integration_name,
      tool_name="generate_data",
      success, duration_ms);
    note right
      Per-task LLM attribution
      (datagen_catalog_generation
      as separate dashboard rows)
      deferred to v0.10
    end note
}

stop
@enduml
