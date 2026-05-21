"use client";

import { useState, useEffect, Suspense } from "react";
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
import { Play, Loader2, EyeOff, Eye } from "lucide-react";
import CopyButton from "@/components/copy-button";

// ─── Tool definitions ────────────────────────────────────────────────────────

type FieldType = "text" | "number" | "textarea" | "select";

interface SelectOption {
  value: string;
  label: string;
}

interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  defaultValue?: string;
  placeholder?: string;
  options?: SelectOption[];
}

interface ToolConfig {
  label: string;
  description: string;
  fields: FieldDef[];
}

const TOOLS: Record<string, ToolConfig> = {
  refine_prompt: {
    label: "Prompt Refiner",
    description: "Enhance and optimize prompts for better AI outputs",
    fields: [
      {
        name: "prompt",
        label: "Prompt",
        type: "textarea",
        required: true,
        placeholder: "Enter your prompt here...",
      },
      {
        name: "domain",
        label: "Domain",
        type: "select",
        defaultValue: "general",
        options: [
          { value: "general", label: "General" },
          { value: "image", label: "Image" },
          { value: "code", label: "Code" },
          { value: "rag", label: "RAG" },
          { value: "llm", label: "LLM" },
        ],
      },
      {
        name: "skill_level",
        label: "Skill level",
        type: "select",
        defaultValue: "intermediate",
        options: [
          { value: "beginner", label: "Beginner" },
          { value: "intermediate", label: "Intermediate" },
          { value: "expert", label: "Expert" },
        ],
      },
    ],
  },
  generate_data: {
    label: "Data Generator",
    description: "Generate realistic mock data in JSON or CSV format",
    fields: [
      {
        name: "rows",
        label: "Rows",
        type: "number",
        required: true,
        defaultValue: "10",
      },
      {
        name: "format",
        label: "Format",
        type: "select",
        required: true,
        defaultValue: "json",
        options: [
          { value: "json", label: "JSON" },
          { value: "csv", label: "CSV" },
        ],
      },
      {
        name: "fields",
        label: "Fields (comma separated)",
        type: "text",
        placeholder: "name, email, phone",
      },
      {
        name: "domain",
        label: "Domain template",
        type: "select",
        defaultValue: "__none__",
        options: [
          { value: "__none__", label: "None (use custom fields)" },
          { value: "ecommerce", label: "E-commerce" },
          { value: "saas", label: "SaaS" },
          { value: "iot_devices", label: "IoT Devices" },
        ],
      },
      {
        name: "realism_level",
        label: "Realism",
        type: "select",
        defaultValue: "basic",
        options: [
          { value: "basic", label: "Basic" },
          { value: "medium", label: "Medium" },
          { value: "high", label: "High" },
        ],
      },
    ],
  },
  rerank_docs: {
    label: "Document Reranker",
    description: "Rerank documents by relevance to a query",
    fields: [
      {
        name: "query",
        label: "Query",
        type: "text",
        required: true,
        placeholder: "machine learning optimization",
      },
      {
        name: "documents_raw",
        label: "Documents (JSON array)",
        type: "textarea",
        required: true,
        placeholder:
          '[{"content": "ML is a subset of AI"}, {"content": "Python is popular for data science"}]',
      },
      {
        name: "top_k",
        label: "Top K results",
        type: "number",
        defaultValue: "5",
      },
    ],
  },
  github_operation: {
    label: "GitHub Operations",
    description: "Natural language GitHub operations",
    fields: [
      {
        name: "query",
        label: "Query",
        type: "text",
        required: true,
        placeholder: "List my repositories",
      },
    ],
  },
};

const LS_API_KEY = "df_playground_api_key";

// ─── Main component (inside Suspense) ────────────────────────────────────────

function PlaygroundContent() {
  const searchParams = useSearchParams();
  const initialTool =
    (searchParams.get("tool") as string) in TOOLS
      ? (searchParams.get("tool") as string)
      : "refine_prompt";

  const [tool, setTool] = useState(initialTool);
  const [values, setValues] = useState<Record<string, string>>({});
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem(LS_API_KEY);
    if (saved) setApiKey(saved);
  }, []);

  const handleToolChange = (next: string) => {
    setTool(next);
    setValues({});
    setResponse(null);
    setError("");
  };

  const val = (name: string) => {
    const field = TOOLS[tool].fields.find((f) => f.name === name);
    return values[name] ?? field?.defaultValue ?? "";
  };

  const setVal = (name: string, v: string) =>
    setValues((prev) => ({ ...prev, [name]: v }));

  const buildArgs = (): Record<string, any> => {
    const args: Record<string, any> = {};
    TOOLS[tool].fields.forEach((f) => {
      const v = val(f.name);
      if (!v || v === "__none__") return;

      if (f.name === "documents_raw") {
        try {
          args["documents"] = JSON.parse(v);
        } catch {
          /* validation catches this */
        }
      } else if (f.name === "fields") {
        args["fields"] = v.split(",").map((s) => s.trim()).filter(Boolean);
      } else if (f.type === "number") {
        args[f.name] = Number(v);
      } else {
        args[f.name] = v;
      }
    });
    return args;
  };

  const validate = (): string | null => {
    if (!apiKey.trim()) return "API key is required to run a request";
    for (const f of TOOLS[tool].fields) {
      const v = val(f.name);
      if (f.required && (!v || v === "__none__")) return `${f.label} is required`;
      if (f.name === "documents_raw" && v) {
        try {
          const p = JSON.parse(v);
          if (!Array.isArray(p)) return "Documents must be a JSON array";
        } catch {
          return "Documents must be valid JSON";
        }
      }
    }
    return null;
  };

  const handleRun = async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError("");
    setLoading(true);
    setResponse(null);
    localStorage.setItem(LS_API_KEY, apiKey);

    try {
      const res = await fetch("/api/proxy/gateway", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
        },
        body: JSON.stringify({ name: tool, arguments: buildArgs() }),
      });
      setResponse(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  const curlText = () => {
    const args = buildArgs();
    const body = JSON.stringify({ name: tool, arguments: args }, null, 2);
    return `curl -X POST http://localhost:8001/api/gateway \\\n  -H "Content-Type: application/json" \\\n  -H "x-api-key: ${apiKey || "YOUR_API_KEY"}" \\\n  -d '${body}'`;
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Playground</h1>
        <p className="text-[rgb(var(--text-muted))]">Test tools interactively</p>
      </div>

      <div className="grid grid-cols-[360px_1fr] gap-6 items-start">
        {/* ── Left panel: config ── */}
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
                  placeholder="df_..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="font-mono text-xs pr-9"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-2.5 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))]"
                  onClick={() => setShowKey((s) => !s)}
                >
                  {showKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
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
              <CardTitle className="text-sm font-medium">Tool</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select value={tool} onValueChange={handleToolChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(TOOLS).map(([k, t]) => (
                    <SelectItem key={k} value={k}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <p className="text-xs text-[rgb(var(--text-muted))] -mt-1">
                {TOOLS[tool].description}
              </p>

              {TOOLS[tool].fields.map((f) => (
                <div key={f.name} className="space-y-1.5">
                  <Label className="text-xs">
                    {f.label}
                    {f.required && <span className="text-[rgb(var(--danger))] ml-1">*</span>}
                  </Label>

                  {f.type === "textarea" ? (
                    <Textarea
                      placeholder={f.placeholder || ""}
                      value={val(f.name)}
                      onChange={(e) => setVal(f.name, e.target.value)}
                      rows={4}
                      className="font-mono text-xs resize-y"
                    />
                  ) : f.type === "select" ? (
                    <Select
                      value={val(f.name)}
                      onValueChange={(v) => setVal(f.name, v)}
                    >
                      <SelectTrigger className="text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {f.options?.map((o) => (
                          <SelectItem key={o.value} value={o.value}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={f.type === "number" ? "number" : "text"}
                      placeholder={f.placeholder || f.defaultValue || ""}
                      value={val(f.name)}
                      onChange={(e) => setVal(f.name, e.target.value)}
                      className="text-sm"
                    />
                  )}
                </div>
              ))}

              {error && <p className="text-xs text-[rgb(var(--danger))]">{error}</p>}

              <Button
                className="w-full"
                onClick={handleRun}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Run
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* ── Right panel: response + curl ── */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium">Response</CardTitle>
              {response && (
                <div className="flex items-center gap-2">
                  <Badge
                    variant={response.success ? "default" : "destructive"}
                    className="text-xs"
                  >
                    {response.success ? "success" : "error"}
                  </Badge>
                  <CopyButton text={JSON.stringify(response, null, 2)} />
                </div>
              )}
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center gap-2 text-[rgb(var(--text-muted))] text-sm py-20 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running...
                </div>
              ) : response ? (
                <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-auto max-h-[520px] whitespace-pre-wrap">
                  {JSON.stringify(response, null, 2)}
                </pre>
              ) : (
                <p className="text-center text-[rgb(var(--text-muted))] py-20 text-sm">
                  Hit <span className="font-mono">Run</span> to see the JSON
                  response
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                curl equivalent
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
        <div className="p-6">
          <div className="h-8 w-40 bg-[rgb(var(--surface-2))] animate-pulse rounded mb-6" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-96 bg-[rgb(var(--surface-2))] animate-pulse rounded" />
            <div className="h-96 bg-[rgb(var(--surface-2))] animate-pulse rounded" />
          </div>
        </div>
      }
    >
      <PlaygroundContent />
    </Suspense>
  );
}
