@startuml
start
:Receive Request (Arguments);

partition "Input Validation" {
    :Validate Rows (1-10000);
    :Validate Format (json/csv);
    
    if (V2 Mode?) then (Yes)
        :Validate Realism (basic/medium/high);
        :Validate Domain (if provided);
    endif
    
    if (Validation Failed?) then (Yes)
        :Return <b>Success: False</b>
        With Error Message;
        stop
    endif
}

if (Prompt or Domain provided?) then (Yes)
    :<b>V2 Mode (Advanced)</b>;
    
    if (ENABLE_SEMANTIC_ANALYZER?) then (Yes)
        :Initialize Semantic Components
        (CatalogFactory, SemanticAnalyzer);
        note right
          <b>Two-Tier Caching</b>
          L1: Request Scope
          L2: Process Scope
        end note
        :Set semantic_generation_used = True;
    else (No)
        :Initialize Basic Generator;
        :Set semantic_generation_used = False;
    endif

    partition "Step 1: Schema Design" {
        if (Prompt provided?) then (Yes)
            :LLM Schema Design
            (Natural Language -> JSON);
        else (No)
            :Load Domain Template
            (e.g., Ecommerce, SaaS);
        endif
    }

    partition "Step 2: Semantic Analysis" {
        :Analyze Schema Fields;
        partition "5-Tier Pipeline" {
            :1. Lexical (Dictionary Match);
            if (found?) then (No)
                :2. Pattern (Regex Match);
                if (found?) then (No)
                    :3. Context (Heuristic);
                    if (found?) then (No)
                        :4. LLM Classification;
                        note right
                          <b>Metadata Only</b>
                          Never generates values
                        end note
                        if (found?) then (No)
                            :5. Fallback (Unknown);
                        endif
                    endif
                endif
            endif
        }
        :Return Semantic Metadata;
    }

    partition "Step 3: Generator Selection & Execution" {
        if (Relationships exist?) then (Yes)
            :Init RelationshipEngine;
            note right: Limitation: Tracking only, no enforcement in Phase 1;
        else (No)
            :Init Independent Generator;
        endif

        :Loop through Entities;
        :Loop through Rows;
        
        partition "Step 4: Value Production" {
            :Select Generator via SemanticRouter;
            
            :Check "Constraint Precedence";
            if (Has Enum?) then (Yes)
                :Enum Generator;
            elseif (Has Pattern?) then (Yes)
                :Regex Generator (rstr);
            elseif (Has Min/Max?) then (Yes)
                :Range Generator;
            else (Default)
                :Semantic Type Generator
                (Faker / Catalog);
            endif
            
            :Generate Value;
        }
        
        :Row Complete;
        :Entity Complete;
    }

    partition "Step 5: Validation & Safety" {
        :Validate Constraints (Invariant 3);
        note right
          <b>Strict Invariants</b>
          - Pattern (Regex)
          - Enum validity
          - Min/Max range
          - Nullability
        end note

        :Validate Foreign Key Integrity;
        :Build FK Integrity Statistics
        (total_children, orphaned_children, etc.);
        
        if (Violations Found?) then (Yes)
            :Build constraint_violations Array;
            :<b>Action: Clear Data</b>;
            :Set Internal Success = False;
        else (No)
            partition "Step 6: Realism (Data Quality)" {
                if (Realism Level > Basic?) then (Yes)
                    if (Is Critical Field?) then (Yes)
                         note right
                           <b>Critical Field Protection</b>
                           Skipped for:
                           - email, phone
                           - uuid, id
                           - date, timestamp
                         end note
                         :Skip Injection;
                    else (No)
                         if (Level == Medium?) then (Yes)
                             :Inject Nulls (~5%);
                         elseif (Level == High?) then (Yes)
                             :Inject Nulls (~10%);
                             :Inject Duplicates (~2%);
                             :Inject Outliers (~1%);
                         endif
                    endif
                endif
            }
            :Set Internal Success = True;
        endif
    }

    partition "Step 7: Observability" {
        :Capture Performance Metrics
        (analysis_ms, generation_ms, total_ms);
        :Build Metadata;
        :Attach Warnings & Confidence;
    }

else (No)
    :<b>V1 Mode (Legacy)</b>;
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
        With Data;
    else (False)
        :Return <b>Success: False</b>
        With Empty Data & Violations;
        note right
          <b>Invariant 8</b>
          Deterministic Success
        end note
    endif
}

stop
@enduml
