"use client";

import { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Play, Loader2, EyeOff, Eye, Plus, X, ChevronDown, ChevronRight, Download,
} from "lucide-react";
import CopyButton from "@/components/copy-button";
import { cn } from "@/lib/utils";

// ─── Tool definitions ────────────────────────────────────────────────────────

type FieldType = "text" | "number" | "textarea" | "select";

interface SelectOption { value: string; label: string; }
interface FieldDef {
  name: string; label: string; type: FieldType;
  required?: boolean; defaultValue?: string; placeholder?: string;
  options?: SelectOption[];
}
interface ToolConfig { label: string; description: string; fields: FieldDef[]; }

const TOOLS: Record<string, ToolConfig> = {
  refine_prompt: {
    label: "Prompt Refiner",
    description: "Optimize prompts for specific domains with evidence-based stack detection",
    fields: [
      { name: "prompt", label: "Prompt", type: "textarea", required: true, placeholder: "Enter your prompt…" },
      {
        name: "domain", label: "Domain", type: "select", defaultValue: "general",
        options: [
          { value: "general", label: "General" },
          { value: "code",    label: "Code" },
          { value: "image",   label: "Image" },
          { value: "rag",     label: "RAG" },
          { value: "llm",     label: "LLM" },
        ],
      },
      {
        name: "skill_level", label: "Skill level", type: "select", defaultValue: "intermediate",
        options: [
          { value: "beginner",     label: "Beginner" },
          { value: "intermediate", label: "Intermediate" },
          { value: "expert",       label: "Expert" },
        ],
      },
    ],
  },
  generate_data: {
    label: "Data Generator",
    description: "V1 (<1s) · V2 multi-entity relational with LLM schema — V2 takes 1–4 min cold",
    fields: [
      { name: "rows", label: "Rows", type: "number", required: true, defaultValue: "10" },
      {
        name: "format", label: "Format", type: "select", required: true, defaultValue: "json",
        options: [{ value: "json", label: "JSON" }, { value: "csv", label: "CSV" }],
      },
      { name: "prompt", label: "Prompt — V2 (LLM schema design)", type: "textarea",
        placeholder: "Generate an e-commerce dataset with customers, orders, and products" },
      {
        name: "domain", label: "Domain template — V2", type: "select", defaultValue: "__none__",
        options: [
          { value: "__none__",    label: "None (V1 or custom prompt)" },
          { value: "ecommerce",   label: "E-commerce — customers · orders · products" },
          { value: "saas",        label: "SaaS — users · subscriptions · usage_logs" },
          { value: "iot_devices", label: "IoT — devices · readings" },
        ],
      },
      { name: "fields", label: "Fields — V1 only (comma separated)", type: "text",
        placeholder: "name, email, phone, company" },
      {
        name: "realism_level", label: "Realism — V2 only", type: "select", defaultValue: "basic",
        options: [
          { value: "basic",  label: "Basic — clean data, no nulls" },
          { value: "medium", label: "Medium — ~5% nulls on nullable fields" },
          { value: "high",   label: "High — 10% nulls, 2% duplicates, 1% outliers" },
        ],
      },
    ],
  },
  rerank_docs: {
    label: "Document Reranker",
    description: "Rerank documents by relevance to a query",
    fields: [
      { name: "query",         label: "Query",                  type: "text",     required: true, placeholder: "machine learning optimization" },
      { name: "documents_raw", label: "Documents (JSON array)", type: "textarea", required: true, placeholder: '[{"content": "ML is a subset of AI"}, {"content": "Python is popular for data science"}]' },
      { name: "top_k",         label: "Top K results",          type: "number",   defaultValue: "5" },
    ],
  },
  github_operation: {
    label: "GitHub Operations",
    description: "Natural language GitHub ops — 26 structured ops via MCP, NL query on both endpoints",
    fields: [
      { name: "query", label: "Query (NL)", type: "text", required: true, placeholder: "List my repositories" },
      {
        name: "risk_confirmed", label: "Confirm Risk", type: "select", defaultValue: "__none__",
        options: [
          { value: "__none__", label: "No (read / low-risk ops)" },
          { value: "true",     label: "Yes — confirmed (HIGH ops)" },
        ],
      },
      { name: "risk_reason", label: "Risk Reason", type: "text", placeholder: "Required for CRITICAL ops (e.g. delete_repo)" },
    ],
  },
  generate_tests: {
    label: "Test Generator",
    description: "Generate ready-to-run unit tests with static validation (parse + import guard)",
    fields: [
      {
        name: "code", label: "Source Code", type: "textarea", required: true,
        placeholder: "def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError\n    return a / b",
      },
      {
        name: "language", label: "Language", type: "select", required: true, defaultValue: "python",
        options: [
          { value: "python",     label: "Python" },
          { value: "javascript", label: "JavaScript" },
          { value: "typescript", label: "TypeScript" },
        ],
      },
      {
        name: "framework", label: "Framework", type: "select", defaultValue: "__none__",
        options: [
          { value: "__none__", label: "Auto (language default)" },
          { value: "pytest",   label: "pytest" },
          { value: "jest",     label: "Jest" },
          { value: "vitest",   label: "Vitest" },
        ],
      },
      { name: "module_path", label: "Module Path", type: "text", placeholder: "src.utils.auth  or  ../src/auth" },
      {
        name: "coverage", label: "Coverage", type: "select", defaultValue: "all",
        options: [
          { value: "all",        label: "All (happy path + edge cases)" },
          { value: "happy_path", label: "Happy path only" },
          { value: "edge_cases", label: "Edge cases only" },
        ],
      },
      {
        name: "use_repo_context", label: "RAG Enrichment", type: "select", defaultValue: "__none__",
        options: [
          { value: "__none__", label: "No (default)" },
          { value: "true",     label: "Yes — use indexed repo" },
        ],
      },
      { name: "instructions", label: "Instructions", type: "text", placeholder: "focus on error paths" },
    ],
  },
};

// ─── refine_prompt manifest options ──────────────────────────────────────────

const MANIFEST_OPTIONS = [
  { value: "requirements.txt", label: "requirements.txt (Python)",   placeholder: "fastapi==0.100.0\nsqlalchemy\npython-jose[cryptography]" },
  { value: "package.json",     label: "package.json (JS / Node)",    placeholder: '{\n  "dependencies": {\n    "react": "^18.0.0",\n    "next": "^14.0.0"\n  }\n}' },
  { value: "go.mod",           label: "go.mod (Go)",                  placeholder: "module myapp\n\ngo 1.21\n\nrequire github.com/gin-gonic/gin v1.9.1" },
  { value: "Cargo.toml",       label: "Cargo.toml (Rust)",           placeholder: '[dependencies]\nactix-web = "4"\ntokio = { version = "1", features = ["full"] }' },
  { value: "pom.xml",          label: "pom.xml (Java)",              placeholder: "<dependency>\n  <groupId>org.springframework.boot</groupId>\n  <artifactId>spring-boot-starter-web</artifactId>\n</dependency>" },
  { value: "Gemfile",          label: "Gemfile (Ruby)",              placeholder: "gem 'rails', '~> 7.0'\ngem 'sidekiq'" },
  { value: "composer.json",    label: "composer.json (PHP)",         placeholder: '{\n  "require": {\n    "laravel/framework": "^10.0"\n  }\n}' },
];

const LS_API_KEY    = "df_playground_api_key";
const LS_GITHUB_PAT = "df_playground_github_pat";

// ─── MCP helpers ─────────────────────────────────────────────────────────────

function buildMcpEnvelope(tool: string, args: Record<string, any>) {
  return { jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: tool, arguments: args } };
}

function parseMcpResponse(raw: any): any {
  // Transport-level JSON-RPC error (e.g. rate limit, schema rejection)
  if (raw.error) {
    return { success: false, error: raw.error.message, data: raw.error.data ?? null };
  }
  const result = raw.result;
  if (!result) return { success: false, error: "No result in MCP response", data: null };
  // Prefer structuredContent (always present when tool returns dict); fall back to content[0].text
  const data =
    result.structuredContent ??
    (() => { try { return JSON.parse(result.content?.[0]?.text ?? "{}"); } catch { return {}; } })();
  return data;
}

// ─── refine_prompt structured response ───────────────────────────────────────

function GroundingBadge({ level }: { level: string }) {
  const cfg =
    level === "high"   ? { bg: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.08)]", text: "text-[rgb(var(--success))]" } :
    level === "medium" ? { bg: "border-yellow-500/30 bg-yellow-500/08",                           text: "text-yellow-500" } :
                         { bg: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.08)]",    text: "text-[rgb(var(--danger))]" };
  return (
    <span className={cn("text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border", cfg.bg, cfg.text)}>
      {level}
    </span>
  );
}

function RefinePromptResult({ response, onShowRaw }: { response: any; onShowRaw: () => void }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const d = response?.data;
  if (!d) return null;

  const stack = d.chosen_stack ?? {};
  const stackCategories = ["languages", "frameworks", "libraries", "services", "databases"] as const;
  const hasStack = stackCategories.some(k => (stack[k] ?? []).length > 0);

  return (
    <div className="space-y-5">
      {/* Quality grounding */}
      {d.quality && (
        <div className={cn(
          "flex flex-wrap items-start gap-2 px-3 py-2.5 rounded-lg border text-xs",
          d.quality.prompt_grounding === "high"   ? "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)]" :
          d.quality.prompt_grounding === "medium" ? "border-yellow-500/30 bg-yellow-500/5"                           :
                                                    "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)]"
        )}>
          <GroundingBadge level={d.quality.prompt_grounding ?? "low"} />
          {d.quality.missing_signals?.length > 0 && (
            <span className="text-[rgb(var(--text-muted))]">
              missing: <span className="font-mono">{d.quality.missing_signals.join(", ")}</span>
            </span>
          )}
          {d.quality.suggested_inputs?.length > 0 && d.quality.prompt_grounding === "low" && (
            <span className="text-[rgb(var(--text-muted))]">
              · add: <span className="font-mono">{d.quality.suggested_inputs.join(", ")}</span>
            </span>
          )}
        </div>
      )}

      {/* Refined prompt */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">Refined Prompt</p>
          <CopyButton text={d.refined_prompt ?? ""} />
        </div>
        <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-auto max-h-[320px] whitespace-pre-wrap leading-relaxed">
          {d.refined_prompt}
        </pre>
      </div>

      {/* Detected stack */}
      {hasStack && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">
              Detected Stack
              {stack.confidence != null && (
                <span className="ml-2 normal-case font-normal">
                  — {(stack.confidence * 100).toFixed(0)}% confidence
                </span>
              )}
            </p>
            {(stack.evidence?.length ?? 0) > 0 && (
              <button
                onClick={() => setShowEvidence(s => !s)}
                className="flex items-center gap-1 text-[10px] text-[rgb(var(--accent))] hover:opacity-80"
              >
                {showEvidence ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Evidence ({stack.evidence.length})
              </button>
            )}
          </div>

          <div className="rounded-lg border border-[rgb(var(--border))] divide-y">
            {stackCategories.map(key => {
              const items: string[] = stack[key] ?? [];
              if (items.length === 0) return null;
              return (
                <div key={key} className="flex items-start gap-4 px-3 py-2">
                  <span className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide w-20 shrink-0 pt-0.5">{key}</span>
                  <div className="flex flex-wrap gap-1.5">
                    {items.map(item => (
                      <Badge key={item} variant="outline" className="text-xs font-mono py-0">{item}</Badge>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {showEvidence && (stack.evidence?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-[rgb(var(--border))] divide-y text-xs">
              {stack.evidence.map((ev: any, i: number) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2">
                  <Badge variant="outline" className="text-xs font-mono shrink-0">{ev.match}</Badge>
                  <span className="text-[rgb(var(--text-muted))] truncate flex-1">
                    {ev.file ? `${ev.file}:${ev.line}` : ev.source}
                    {ev.excerpt ? <span className="ml-2 font-mono opacity-60">{ev.excerpt}</span> : null}
                  </span>
                  <span className="text-[rgb(var(--text-muted))] shrink-0 font-mono">{ev.confidence_hint ?? ev.weight?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Context summary */}
      {d.context_summary && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">Context Summary</p>
          <pre className="bg-[rgb(var(--surface-2))] text-[rgb(var(--text))] font-mono text-xs rounded-lg p-3 whitespace-pre-wrap">
            {d.context_summary}
          </pre>
        </div>
      )}

      {/* Sanitization warnings */}
      {d.sanitization_log?.length > 0 && (
        <div className="rounded-lg border border-[rgb(var(--warning)/0.3)] bg-[rgb(var(--warning)/0.06)] px-3 py-2 text-xs text-[rgb(var(--warning))]">
          {d.sanitization_log.length} sanitization event{d.sanitization_log.length > 1 ? "s" : ""} — secrets/injections redacted
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-[rgb(var(--border))]">
        <button
          onClick={onShowRaw}
          className="flex items-center gap-1 text-xs text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
        >
          <ChevronRight className="h-3 w-3" />
          Raw JSON
        </button>
        {response.execution_time != null && (
          <span className="text-xs text-[rgb(var(--text-muted))] font-mono">{response.execution_time.toFixed(1)}s</span>
        )}
      </div>
    </div>
  );
}

// ─── generate_tests structured response ──────────────────────────────────────

function ValidatedBadge({ level }: { level: string }) {
  const cfg =
    level === "static"  ? { bg: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.08)]", text: "text-[rgb(var(--success))]" } :
    level === "partial" ? { bg: "border-yellow-500/30 bg-yellow-500/08",                           text: "text-yellow-500" } :
                          { bg: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.08)]",    text: "text-[rgb(var(--danger))]" };
  return (
    <span className={cn("text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded border", cfg.bg, cfg.text)}>
      {level}
    </span>
  );
}

function GenerateTestsResult({ response, onShowRaw }: { response: any; onShowRaw: () => void }) {
  const d = response?.data;
  if (!d) return null;

  const subtitleMap: Record<string, string> = {
    static:      "parse ✓ · imports ✓",
    partial:     "parse ✓ · some imports unresolved",
    unparseable: "syntax errors in generated output",
  };

  return (
    <div className="space-y-5">
      {/* Validated status + filename */}
      <div className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg border border-[rgb(var(--border))]">
        <div className="flex items-center gap-2.5">
          <ValidatedBadge level={d.validated ?? "unparseable"} />
          <span className="text-xs text-[rgb(var(--text-muted))]">
            {subtitleMap[d.validated] ?? ""}
          </span>
        </div>
        {d.filename && (
          <span className="text-xs font-mono text-[rgb(var(--text-muted))] shrink-0">{d.filename}</span>
        )}
      </div>

      {/* Test file */}
      {d.test_file && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">Test File</p>
            <CopyButton text={d.test_file} />
          </div>
          <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-auto max-h-[360px] whitespace-pre-wrap leading-relaxed">
            {d.test_file}
          </pre>
        </div>
      )}

      {/* Test cases */}
      {(d.cases?.length ?? 0) > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">
            Test Cases{" "}
            <span className="font-normal normal-case">({d.cases.length})</span>
          </p>
          <div className="rounded-lg border border-[rgb(var(--border))] divide-y">
            {d.cases.map((c: any, i: number) => (
              <div key={i} className="flex items-start gap-3 px-3 py-2">
                <span className="text-xs font-mono text-[rgb(var(--text))] flex-1 min-w-0 truncate">{c.name}</span>
                {c.asserts && (
                  <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] truncate max-w-[200px] shrink-0">{c.asserts}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unresolved symbols */}
      {(d.unresolved_symbols?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-3 py-2.5 space-y-1.5">
          <p className="text-[10px] font-semibold text-yellow-500 uppercase tracking-widest">Unresolved Imports</p>
          <div className="flex flex-wrap gap-1.5">
            {d.unresolved_symbols.map((sym: string) => (
              <Badge key={sym} variant="outline" className="text-xs font-mono text-yellow-500 border-yellow-500/40">{sym}</Badge>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {(d.warnings?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-[rgb(var(--warning)/0.3)] bg-[rgb(var(--warning)/0.06)] px-3 py-2 space-y-0.5">
          {d.warnings.map((w: string, i: number) => (
            <p key={i} className="text-xs text-[rgb(var(--warning))]">{w}</p>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-[rgb(var(--border))]">
        <button
          onClick={onShowRaw}
          className="flex items-center gap-1 text-xs text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
        >
          <ChevronRight className="h-3 w-3" />
          Raw JSON
        </button>
        <div className="flex items-center gap-3 text-xs font-mono text-[rgb(var(--text-muted))]">
          {d.repo_context_used && (
            <span className="text-[rgb(var(--accent))]">RAG ✓</span>
          )}
          {response.tokens_used != null && (
            <span>{response.tokens_used} tok</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── generate_data helpers + structured response ─────────────────────────────

type DataRow = Record<string, unknown>;

interface NormalizedDataset {
  mode: "v1" | "v2";
  entities: string[];
  rows: Record<string, DataRow[]>;
  csvRaw?: string;
  metadata?: any;
  fkIntegrity?: any;
  totalRows: number;
  totalColumns: number;
}

function normalizeGenerateData(d: any): NormalizedDataset | null {
  if (!d) return null;
  // V2: has entities array + data object
  if (Array.isArray(d.entities) && d.entities.length > 0 && d.data && !Array.isArray(d.data)) {
    const entities: string[] = d.entities.filter((e: any) => typeof e === "string");
    const rows: Record<string, DataRow[]> = {};
    for (const e of entities) {
      const raw = (d.data as any)[e];
      rows[e] = Array.isArray(raw) ? raw.filter((r: any) => r && typeof r === "object") : [];
    }
    const totalRows = entities.reduce((s, e) => s + rows[e].length, 0);
    const totalColumns = new Set(entities.flatMap(e => Object.keys(rows[e]?.[0] ?? {}))).size;
    return { mode: "v2", entities, rows, metadata: d.metadata, fkIntegrity: d.fk_integrity, totalRows, totalColumns };
  }
  // V1: data is a JSON or CSV string
  if (typeof d.data === "string" && d.data.length > 0) {
    if (d.format === "csv") {
      return { mode: "v1", entities: [], rows: {}, csvRaw: d.data, totalRows: d.rows ?? 0, totalColumns: 0 };
    }
    try {
      const parsed = JSON.parse(d.data);
      if (Array.isArray(parsed)) {
        const cleaned = parsed.filter((r: any) => r && typeof r === "object") as DataRow[];
        const cols = Object.keys(cleaned[0] ?? {}).length;
        return { mode: "v1", entities: ["rows"], rows: { rows: cleaned }, totalRows: cleaned.length, totalColumns: cols };
      }
    } catch {}
  }
  return null;
}

function cellStr(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.style.display = "none";
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

function GenerateDataResult({ response, onShowRaw }: { response: any; onShowRaw: () => void }) {
  // min-w-0 is critical — without it this component can overflow the grid column
  const d = response?.data;
  const dataset = useMemo(() => normalizeGenerateData(d), [d]);
  const [activeEntity, setActiveEntity] = useState<string>("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (dataset?.entities.length && !dataset.entities.includes(activeEntity)) {
      setActiveEntity(dataset.entities[0]);
      setExpanded(false);
    }
  }, [dataset]);

  if (!dataset) return null;

  const currentRows: DataRow[] = dataset.rows[activeEntity] ?? [];
  const columns = currentRows.length > 0 ? Object.keys(currentRows[0]) : [];
  const displayRows = expanded ? currentRows : currentRows.slice(0, 10);
  const hasMore = currentRows.length > 10;

  function downloadCSV() {
    if (!currentRows.length) return;
    const header = columns.join(",");
    const body = currentRows.map(row =>
      columns.map(col => {
        const s = cellStr(row[col]).replace(/"/g, '""');
        return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s}"` : s;
      }).join(",")
    );
    triggerBlobDownload(new Blob([[header, ...body].join("\n")], { type: "text/csv" }), `${activeEntity || "data"}.csv`);
  }

  function downloadJSON() {
    const payload = dataset!.mode === "v2" ? { entities: dataset!.entities, data: dataset!.rows } : currentRows;
    triggerBlobDownload(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }), "generated_data.json");
  }

  const semSummary = dataset.metadata?.semantic_analysis_summary;
  const fk = dataset.fkIntegrity;

  // CSV raw view (V1 CSV mode)
  if (dataset.csvRaw) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">CSV Output</p>
          <span className="text-xs font-mono text-[rgb(var(--text-muted))]">{dataset.totalRows} rows</span>
        </div>
        <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-auto max-h-[360px] whitespace-pre leading-relaxed">
          {dataset.csvRaw.split("\n").slice(0, 50).join("\n")}
          {dataset.csvRaw.split("\n").length > 50 && "\n…"}
        </pre>
        <div className="flex items-center justify-between pt-1 border-t border-[rgb(var(--border))]">
          <button onClick={onShowRaw} className="flex items-center gap-1 text-xs text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]">
            <ChevronRight className="h-3 w-3" /> Raw JSON
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 min-w-0 overflow-hidden">
      {/* Header: stats + downloads */}
      <div className="rounded-lg border border-[rgb(var(--border))] p-3 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold">Generated Dataset</p>
            <p className="text-[10px] text-[rgb(var(--text-muted))] mt-0.5">
              {dataset.mode === "v2"
                ? `${dataset.entities.length} ${dataset.entities.length === 1 ? "entity" : "entities"}`
                : "1 table"}
              {" · "}{dataset.totalRows.toLocaleString()} rows
              {dataset.totalColumns > 0 && ` · ${dataset.totalColumns} columns`}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              onClick={downloadCSV}
              disabled={!currentRows.length}
              className="flex items-center gap-1 text-xs border border-[rgb(var(--border))] rounded-md px-2 py-1 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))] hover:bg-[rgb(var(--surface-2))] disabled:opacity-40 transition-colors"
            >
              <Download className="h-3 w-3" /> CSV
            </button>
            <button
              onClick={downloadJSON}
              className="flex items-center gap-1 text-xs border border-[rgb(var(--border))] rounded-md px-2 py-1 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))] hover:bg-[rgb(var(--surface-2))] transition-colors"
            >
              <Download className="h-3 w-3" /> JSON
            </button>
          </div>
        </div>

        {/* Entity tabs */}
        {dataset.mode === "v2" && dataset.entities.length > 1 && (
          <div className="flex gap-1 overflow-x-auto">
            {dataset.entities.map(entity => (
              <button
                key={entity}
                onClick={() => { setActiveEntity(entity); setExpanded(false); }}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium shrink-0 transition-colors",
                  activeEntity === entity
                    ? "bg-[rgb(var(--accent-subtle))] text-[rgb(var(--accent))] border border-[rgb(var(--accent)/0.2)]"
                    : "text-[rgb(var(--text-muted))] hover:bg-[rgb(var(--surface-2))] border border-transparent"
                )}
              >
                {entity}
                <span className="rounded bg-[rgb(var(--surface-2))] px-1 text-[10px]">
                  {dataset.rows[entity]?.length ?? 0}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      {columns.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-widest">
              {activeEntity || "rows"}
              <span className="font-normal normal-case"> · {currentRows.length} rows · {columns.length} cols</span>
            </p>
            {!expanded && hasMore && (
              <span className="text-[10px] text-[rgb(var(--text-muted))]">Previewing first 10</span>
            )}
          </div>
          <div className="rounded-lg border border-[rgb(var(--border))] overflow-hidden">
            <div className="overflow-x-auto overflow-y-auto max-h-[300px]">
              <table className="w-full text-xs table-fixed">
                <colgroup>
                  <col className="w-8" />
                  {columns.map(col => (
                    <col key={col} style={{ width: "120px", minWidth: "80px", maxWidth: "180px" }} />
                  ))}
                </colgroup>
                <thead className="sticky top-0 bg-[rgb(var(--surface-2))] border-b border-[rgb(var(--border))]">
                  <tr>
                    <th className="px-2 py-2 text-left font-medium text-[rgb(var(--text-muted))]">#</th>
                    {columns.map(col => (
                      <th key={col} className="px-2 py-2 text-left font-medium text-[rgb(var(--text-muted))] truncate">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgb(var(--border))]">
                  {displayRows.map((row, i) => (
                    <tr key={i} className="hover:bg-[rgb(var(--surface-2)/0.4)] transition-colors">
                      <td className="px-2 py-1.5 font-mono text-[10px] text-[rgb(var(--text-muted))]">{i + 1}</td>
                      {columns.map(col => (
                        <td key={col} className="px-2 py-1.5 truncate font-mono text-[11px]" title={cellStr(row[col])}>
                          {row[col] == null
                            ? <span className="text-[rgb(var(--text-muted))] opacity-50">null</span>
                            : cellStr(row[col])
                          }
                        </td>
                      ))}
                    </tr>
                  ))}
                  {hasMore && !expanded && (
                    <tr>
                      <td colSpan={columns.length + 1} className="px-2 py-2 text-center text-[10px] bg-[rgb(var(--surface-2)/0.3)]">
                        <button onClick={() => setExpanded(true)} className="text-[rgb(var(--accent))] hover:underline">
                          + {currentRows.length - 10} more rows — show all {currentRows.length}
                        </button>
                      </td>
                    </tr>
                  )}
                  {expanded && hasMore && (
                    <tr>
                      <td colSpan={columns.length + 1} className="px-2 py-2 text-center text-[10px]">
                        <button onClick={() => setExpanded(false)} className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]">
                          Collapse
                        </button>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* FK integrity */}
      {fk && (
        <div className={cn(
          "rounded-lg border px-3 py-2 text-xs flex items-center gap-2",
          fk.valid
            ? "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)] text-[rgb(var(--success))]"
            : "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)] text-[rgb(var(--danger))]"
        )}>
          {fk.valid ? "✓ FK integrity: all relationships valid" : `✗ FK integrity errors: ${fk.errors?.length ?? 0}`}
          {fk.valid && fk.statistics && (
            <span className="text-[rgb(var(--text-muted))] ml-1">
              · {Object.keys(fk.statistics).length} relationship{Object.keys(fk.statistics).length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {/* Semantic analysis */}
      {semSummary && (
        <div className="rounded-lg border border-[rgb(var(--success)/0.25)] bg-[rgb(var(--success)/0.04)] px-3 py-2.5 text-xs space-y-1">
          <p className="font-semibold text-[rgb(var(--success))]">
            Semantic analysis
            {semSummary.avg_confidence != null && (
              <span className="font-normal text-[rgb(var(--text-muted))] ml-2">
                {Math.round((semSummary.avg_confidence as number) * 100)}% confidence
                {semSummary.total_fields != null && ` · ${semSummary.total_fields} fields`}
              </span>
            )}
          </p>
          {semSummary.summary && (
            <p className="text-[rgb(var(--text-muted))] leading-relaxed">{String(semSummary.summary)}</p>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-[rgb(var(--border))]">
        <button onClick={onShowRaw} className="flex items-center gap-1 text-xs text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]">
          <ChevronRight className="h-3 w-3" /> Raw JSON
        </button>
        <div className="flex items-center gap-3 text-xs font-mono text-[rgb(var(--text-muted))]">
          {d?.semantic_generation_used && <span className="text-[rgb(var(--accent))]">semantic ✓</span>}
          {d?.mode && <span>{String(d.mode)}</span>}
        </div>
      </div>
    </div>
  );
}

// ─── Main component (inside Suspense) ────────────────────────────────────────

function PlaygroundContent() {
  const searchParams = useSearchParams();
  const initialTool =
    (searchParams.get("tool") as string) in TOOLS
      ? (searchParams.get("tool") as string)
      : "refine_prompt";

  const [tool, setTool]         = useState(initialTool);
  const [values, setValues]     = useState<Record<string, string>>({});
  const [apiKey, setApiKey]     = useState("");
  const [showKey, setShowKey]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [response, setResponse] = useState<any>(null);
  const [error, setError]       = useState("");

  // Protocol toggle — default to MCP
  const [protocol, setProtocol] = useState<"mcp" | "rest">("mcp");

  // refine_prompt extras
  const [attachedFiles,   setAttachedFiles]   = useState<string[]>([""]);
  const [manifestType,    setManifestType]    = useState("requirements.txt");
  const [manifestContent, setManifestContent] = useState("");
  const [showRawJson,     setShowRawJson]     = useState(false);

  // github_operation extras
  const [githubPat,     setGithubPat]     = useState("");
  const [showGithubPat, setShowGithubPat] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(LS_API_KEY);
    if (saved) setApiKey(saved);
    const savedPat = localStorage.getItem(LS_GITHUB_PAT);
    if (savedPat) setGithubPat(savedPat);
  }, []);

  const handleToolChange = (next: string) => {
    setTool(next);
    setValues({});
    setResponse(null);
    setError("");
    setAttachedFiles([""]);
    setManifestType("requirements.txt");
    setManifestContent("");
    setShowRawJson(false);
  };

  const val = (name: string) => {
    const field = TOOLS[tool].fields.find(f => f.name === name);
    return values[name] ?? field?.defaultValue ?? "";
  };
  const setVal = (name: string, v: string) =>
    setValues(prev => ({ ...prev, [name]: v }));

  const buildArgs = (): Record<string, any> => {
    const args: Record<string, any> = {};
    TOOLS[tool].fields.forEach(f => {
      const v = val(f.name);
      if (!v || v === "__none__") return;
      if (f.name === "documents_raw") {
        try { args["documents"] = JSON.parse(v); } catch { /* validation catches */ }
      } else if (f.name === "fields") {
        args["fields"] = v.split(",").map(s => s.trim()).filter(Boolean);
      } else if (f.type === "number") {
        args[f.name] = Number(v);
      } else {
        args[f.name] = v;
      }
    });
    // refine_prompt-specific context
    if (tool === "refine_prompt") {
      const files = attachedFiles.filter(f => f.trim());
      if (files.length > 0) args.attached_files = files;
      if (manifestContent.trim()) args.project_files = { [manifestType]: manifestContent.trim() };
    }
    // generate_tests: coerce use_repo_context to boolean
    if (tool === "generate_tests" && args.use_repo_context === "true") {
      args.use_repo_context = true;
    }
    // github_operation: build context object with PAT + risk fields
    if (tool === "github_operation") {
      const ctx: Record<string, any> = {};
      if (githubPat.trim()) ctx.github_token = githubPat.trim();
      if (args.risk_confirmed === "true") ctx.risk_confirmed = true;
      if (args.risk_reason) ctx.risk_reason = args.risk_reason;
      if (Object.keys(ctx).length > 0) args.context = ctx;
      delete args.risk_confirmed;
      delete args.risk_reason;
    }
    return args;
  };

  const validate = (): string | null => {
    if (!apiKey.trim()) return "API key is required to run a request";
    for (const f of TOOLS[tool].fields) {
      const v = val(f.name);
      if (f.required && (!v || v === "__none__")) return `${f.label} is required`;
      if (f.name === "documents_raw" && v) {
        try {
          if (!Array.isArray(JSON.parse(v))) return "Documents must be a JSON array";
        } catch { return "Documents must be valid JSON"; }
      }
    }
    return null;
  };

  const handleRun = async () => {
    const err = validate();
    if (err) { setError(err); return; }
    setError("");
    setLoading(true);
    setResponse(null);
    setShowRawJson(false);
    localStorage.setItem(LS_API_KEY, apiKey);
    if (githubPat.trim()) localStorage.setItem(LS_GITHUB_PAT, githubPat.trim());

    try {
      const args = buildArgs();
      const isMcp = protocol === "mcp";
      const url  = isMcp ? "/api/proxy/mcp" : "/api/proxy/gateway";
      const body = isMcp
        ? JSON.stringify(buildMcpEnvelope(tool, args))
        : JSON.stringify({ name: tool, arguments: args });

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey },
        body,
      });
      const raw = await res.json();
      setResponse(isMcp ? parseMcpResponse(raw) : raw);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const curlText = () => {
    const args = buildArgs();
    if (protocol === "mcp") {
      const body = JSON.stringify(buildMcpEnvelope(tool, args), null, 2);
      return (
        `curl -i -X POST http://localhost:8001/mcp/ \\\n` +
        `  -H "Content-Type: application/json" \\\n` +
        `  -H "Accept: application/json, text/event-stream" \\\n` +
        `  -H "x-api-key: ${apiKey || "YOUR_API_KEY"}" \\\n` +
        `  -d '${body}'`
      );
    }
    const body = JSON.stringify({ name: tool, arguments: args }, null, 2);
    return (
      `curl -X POST http://localhost:8001/api/gateway \\\n` +
      `  -H "Content-Type: application/json" \\\n` +
      `  -H "x-api-key: ${apiKey || "YOUR_API_KEY"}" \\\n` +
      `  -d '${body}'`
    );
  };

  const activeManifestOption = MANIFEST_OPTIONS.find(o => o.value === manifestType);
  const isRefinePrompt    = tool === "refine_prompt";
  const isGenerateTests   = tool === "generate_tests";
  const isGithubOperation = tool === "github_operation";
  const isGenerateData    = tool === "generate_data";
  const showStructuredResult =
    (isRefinePrompt || isGenerateTests || isGenerateData) && response?.success && response?.data && !showRawJson;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Playground</h1>
        <p className="text-[rgb(var(--text-muted))] mt-1">Test tools interactively against live endpoints</p>
      </div>

      <div className="grid grid-cols-[360px_1fr] gap-6 items-start">
        {/* ── Left panel ── */}
        <div className="space-y-4">
          {/* API key */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">API Key</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <Input
                  type={showKey ? "text" : "password"}
                  placeholder="df_…"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  className="font-mono text-xs pr-9"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-2.5 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
                  onClick={() => setShowKey(s => !s)}
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="text-xs text-[rgb(var(--text-muted))] mt-1.5">
                Saved locally. Get yours from API Keys.
              </p>
            </CardContent>
          </Card>

          {/* Tool + fields */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Request</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Protocol toggle */}
              <div className="space-y-1.5">
                <Label className="text-xs text-[rgb(var(--text-muted))]">Protocol</Label>
                <div className="flex items-center gap-0.5 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--surface-2))] p-0.5">
                  {(["mcp", "rest"] as const).map(p => (
                    <button
                      key={p}
                      onClick={() => setProtocol(p)}
                      className={cn(
                        "flex-1 text-xs px-3 py-1.5 rounded-md font-medium transition-all",
                        protocol === p
                          ? "bg-[rgb(var(--surface))] text-[rgb(var(--text))] shadow-sm"
                          : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
                      )}
                    >
                      {p === "mcp" ? "MCP  /mcp/" : "REST  /api/gateway"}
                    </button>
                  ))}
                </div>
                {protocol === "mcp" && (
                  <p className="text-[10px] text-[rgb(var(--accent))]">
                    JSON-RPC 2.0 — same transport as Cursor / Claude Desktop
                  </p>
                )}
              </div>

              {/* Tool selector */}
              <div className="space-y-1.5">
                <Label className="text-xs">Tool</Label>
                <Select value={tool} onValueChange={handleToolChange}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(TOOLS).map(([k, t]) => (
                      <SelectItem key={k} value={k}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-[rgb(var(--text-muted))]">{TOOLS[tool].description}</p>
              </div>

              {/* Generic fields */}
              {TOOLS[tool].fields.map(f => (
                <div key={f.name} className="space-y-1.5">
                  <Label className="text-xs">
                    {f.label}
                    {f.required && <span className="text-[rgb(var(--danger))] ml-1">*</span>}
                  </Label>
                  {f.type === "textarea" ? (
                    <Textarea
                      placeholder={f.placeholder || ""}
                      value={val(f.name)}
                      onChange={e => setVal(f.name, e.target.value)}
                      rows={4}
                      className="font-mono text-xs resize-y"
                    />
                  ) : f.type === "select" ? (
                    <Select value={val(f.name)} onValueChange={v => setVal(f.name, v)}>
                      <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {f.options?.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={f.type === "number" ? "number" : "text"}
                      placeholder={f.placeholder || f.defaultValue || ""}
                      value={val(f.name)}
                      onChange={e => setVal(f.name, e.target.value)}
                      className="text-sm"
                    />
                  )}
                </div>
              ))}

              {/* ── refine_prompt extras ── */}
              {isRefinePrompt && (
                <>
                  <div className="border-t border-[rgb(var(--border))] pt-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">
                        Code Files
                        <span className="text-[rgb(var(--text-muted))] font-normal ml-1">optional</span>
                      </Label>
                      <button
                        type="button"
                        onClick={() => setAttachedFiles(prev => [...prev, ""])}
                        className="flex items-center gap-1 text-xs text-[rgb(var(--accent))] hover:opacity-80"
                      >
                        <Plus className="h-3 w-3" />
                        Add file
                      </button>
                    </div>
                    <p className="text-[10px] text-[rgb(var(--text-muted))]">
                      Paste code snippets — tool extracts imports &amp; class names for stack detection
                    </p>
                    {attachedFiles.map((f, i) => (
                      <div key={i} className="relative">
                        <Textarea
                          value={f}
                          onChange={e => setAttachedFiles(prev => prev.map((p, j) => j === i ? e.target.value : p))}
                          placeholder={`# File ${i + 1}\nfrom fastapi import FastAPI\napp = FastAPI()`}
                          rows={3}
                          className="font-mono text-xs resize-y pr-7"
                        />
                        {attachedFiles.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setAttachedFiles(prev => prev.filter((_, j) => j !== i))}
                            className="absolute top-1.5 right-1.5 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--danger))]"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs">
                      Project Manifest
                      <span className="text-[rgb(var(--text-muted))] font-normal ml-1">optional</span>
                    </Label>
                    <p className="text-[10px] text-[rgb(var(--text-muted))]">
                      Dependency file — strongest evidence signal (0.9 weight)
                    </p>
                    <Select value={manifestType} onValueChange={setManifestType}>
                      <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {MANIFEST_OPTIONS.map(o => (
                          <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Textarea
                      value={manifestContent}
                      onChange={e => setManifestContent(e.target.value)}
                      placeholder={activeManifestOption?.placeholder ?? ""}
                      rows={3}
                      className="font-mono text-xs resize-y"
                    />
                  </div>
                </>
              )}

              {/* ── github_operation: PAT token ── */}
              {isGithubOperation && (
                <div className="border-t border-[rgb(var(--border))] pt-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs">
                      GitHub PAT
                      <span className="text-[rgb(var(--danger))] ml-1">*</span>
                    </Label>
                    <button
                      type="button"
                      onClick={() => setShowGithubPat(s => !s)}
                      className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
                    >
                      {showGithubPat ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <Input
                    type={showGithubPat ? "text" : "password"}
                    placeholder="ghp_…"
                    value={githubPat}
                    onChange={e => setGithubPat(e.target.value)}
                    className="font-mono text-xs"
                  />
                  <p className="text-[10px] text-[rgb(var(--text-muted))]">
                    Sent as <span className="font-mono">context.github_token</span>. Saved locally.
                  </p>
                </div>
              )}

              {error && <p className="text-xs text-[rgb(var(--danger))]">{error}</p>}

              <Button className="w-full" onClick={handleRun} disabled={loading}>
                {loading
                  ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  : <Play className="h-4 w-4 mr-2" />}
                Run
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* ── Right panel ── */}
        <div className="space-y-4 min-w-0">
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium">Response</CardTitle>
              {response && (
                <div className="flex items-center gap-2">
                  <Badge variant={response.success ? "default" : "destructive"} className="text-xs">
                    {response.success ? "success" : "error"}
                  </Badge>
                  {showStructuredResult ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setShowRawJson(true)}
                    >
                      Raw JSON
                    </Button>
                  ) : (
                    <>
                      {(isRefinePrompt || isGenerateTests || isGenerateData) && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => setShowRawJson(false)}
                        >
                          Structured
                        </Button>
                      )}
                      <CopyButton text={JSON.stringify(response, null, 2)} />
                    </>
                  )}
                </div>
              )}
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex flex-col items-center gap-2 text-[rgb(var(--text-muted))] text-sm py-20 justify-center">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Running…
                  {isGenerateData && (
                    <p className="text-[10px] text-center max-w-[260px] mt-1 leading-relaxed opacity-75">
                      V2 datasets take 1–4 min — LLM schema design + per-entity catalog generation
                    </p>
                  )}
                </div>
              ) : showStructuredResult ? (
                isRefinePrompt
                  ? <RefinePromptResult response={response} onShowRaw={() => setShowRawJson(true)} />
                  : isGenerateTests
                  ? <GenerateTestsResult response={response} onShowRaw={() => setShowRawJson(true)} />
                  : <GenerateDataResult response={response} onShowRaw={() => setShowRawJson(true)} />
              ) : response ? (
                <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-auto max-h-[520px] whitespace-pre-wrap">
                  {JSON.stringify(response, null, 2)}
                </pre>
              ) : (
                <p className="text-center text-[rgb(var(--text-muted))] py-20 text-sm">
                  Hit <span className="font-mono">Run</span> to see the response
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                {protocol === "mcp" ? "curl (MCP / JSON-RPC 2.0)" : "curl (REST)"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-x-auto whitespace-pre">
                  {curlText()}
                </pre>
                <CopyButton text={curlText()} />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function PlaygroundPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="h-9 w-48 bg-[rgb(var(--surface-2))] animate-pulse rounded" />
          <div className="grid grid-cols-[360px_1fr] gap-6">
            <div className="h-[600px] bg-[rgb(var(--surface-2))] animate-pulse rounded-xl" />
            <div className="h-[600px] bg-[rgb(var(--surface-2))] animate-pulse rounded-xl" />
          </div>
        </div>
      }
    >
      <PlaygroundContent />
    </Suspense>
  );
}
