"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import CopyButton from "@/components/copy-button";
import {
  Wand2, Database, FileCode, Github, FlaskConical, CheckCircle2,
  TestTube2, Plus, Minus,
} from "lucide-react";

// ─── Code examples ────────────────────────────────────────────────────────────

const mcpQuickStart = `curl -i -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "refine_prompt",
      "arguments": { "prompt": "add authentication" }
    }
  }'`;

const restQuickStart = `curl -X POST http://localhost:8001/api/gateway \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "name": "refine_prompt",
    "arguments": { "prompt": "add authentication" }
  }'`;

const mcpConfig = `{
  "mcpServers": {
    "devforge": {
      "url": "http://localhost:8001/mcp/",
      "headers": {
        "x-api-key": "YOUR_API_KEY"
      }
    }
  }
}`;

// ─── refine_prompt examples ───────────────────────────────────────────────────

const refineBasic = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "refine_prompt",
      "arguments": {
        "prompt": "write a login page",
        "domain": "code",
        "skill_level": "intermediate"
      }
    }
  }'`;

const refineWithContext = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "refine_prompt",
      "arguments": {
        "prompt": "add authentication",
        "domain": "code",
        "project_files": {
          "requirements.txt": "fastapi==0.100.0\\npython-jose[cryptography]"
        },
        "attached_files": [
          "from fastapi import FastAPI\\nclass UserModel:\\n    pass"
        ]
      }
    }
  }'`;

const refineResponse = `{
  "success": true,
  "tool": "refine_prompt",
  "data": {
    "refined_prompt": "Implement JWT authentication using FastAPI and python-jose...",
    "context_summary": "- Language: python\\n- Frameworks: FastAPI\\n- Classes: UserModel",
    "chosen_stack": {
      "languages":  ["python"],
      "frameworks": ["FastAPI"],
      "libraries":  ["python-jose"],
      "services":   [],
      "databases":  [],
      "confidence": 0.85,
      "evidence": [
        {
          "match": "FastAPI",
          "source": "dependency_analysis",
          "file": "requirements.txt",
          "line": 1,
          "weight": 0.9,
          "confidence_hint": "strong"
        }
      ]
    },
    "quality": {
      "prompt_grounding": "medium",
      "missing_signals": ["database"],
      "suggested_inputs": []
    },
    "sanitization_log": [],
    "domain": "code"
  },
  "execution_time": 11.49
}`;

const mcpResponseShape = `{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "structuredContent": { /* same shape as gateway data above */ },
    "content": [{ "type": "text", "text": "{ ... same as JSON string ... }" }],
    "isError": false
  }
}`;

// ─── github_operation examples ───────────────────────────────────────────────

const githubNlListRepos = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "query": "list my repositories",
        "context": { "github_token": "ghp_YOUR_PAT" }
      }
    }
  }'`;

const githubStructuredCreateIssue = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "github_operation",
      "arguments": {
        "operation": "create_issue",
        "repo_name": "owner/repo",
        "title": "Bug: login fails on Safari",
        "body": "Steps to reproduce...",
        "labels": ["bug"],
        "context": { "github_token": "ghp_YOUR_PAT" }
      }
    }
  }'`;

const githubHighOpExample = `curl -X POST http://localhost:8001/mcp/ \\
  ...
  "arguments": {
    "operation": "create_repo",
    "name": "my-new-repo",
    "private": true,
    "context": {
      "github_token": "ghp_YOUR_PAT",
      "risk_confirmed": true
    }
  }`;

const githubCriticalOpExample = `curl -X POST http://localhost:8001/mcp/ \\
  ...
  "arguments": {
    "operation": "delete_repo",
    "repo_name": "owner/repo",
    "context": {
      "github_token": "ghp_YOUR_PAT",
      "risk_confirmed": true,
      "risk_reason": "Decommissioning after migration to new org"
    }
  }`;

const githubGatewayNl = `curl -X POST http://localhost:8001/api/gateway \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "name": "github_operation",
    "arguments": {
      "query": "list open pull requests in owner/repo",
      "context": { "github_token": "ghp_YOUR_PAT" }
    }
  }'`;

// ─── generate_tests examples ──────────────────────────────────────────────────

const generateTestsPython = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "generate_tests",
      "arguments": {
        "code": "def add(a, b):\\n    return a + b\\n\\ndef divide(a, b):\\n    if b == 0:\\n        raise ValueError\\n    return a / b",
        "language": "python",
        "module_path": "src.calc"
      }
    }
  }'`;

const generateTestsTypescript = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "generate_tests",
      "arguments": {
        "code": "export function verifyToken(t: string): boolean { ... }",
        "language": "typescript",
        "framework": "vitest",
        "module_path": "../src/auth",
        "coverage": "edge_cases",
        "instructions": "focus on expired and malformed tokens"
      }
    }
  }'`;

const generateTestsResponse = `{
  "success": true,
  "data": {
    "framework": "pytest",
    "language": "python",
    "filename": "test_calc.py",
    "test_file": "import pytest\\nfrom src.calc import add, divide\\n\\ndef test_add_returns_sum():\\n    assert add(1, 2) == 3\\n...",
    "cases": [
      { "name": "test_add_returns_sum",         "asserts": "assert add(1, 2) == 3" },
      { "name": "test_divide_zero_denominator",  "asserts": "" },
      { "name": "test_divide_normal_cases",      "asserts": "assert divide(n, d) == expected" }
    ],
    "unresolved_symbols": [],
    "validated": "static",
    "coverage": "all",
    "repo_context_used": false,
    "warnings": []
  },
  "format": "code",
  "tokens_used": 582
}`;

// ─── generate_data examples ──────────────────────────────────────────────────

const generateDataV1 = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "generate_data",
      "arguments": {
        "rows": 50,
        "format": "json",
        "fields": ["name", "email", "phone", "company"]
      }
    }
  }'`;

const generateDataV2Domain = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "generate_data",
      "arguments": {
        "rows": 500,
        "domain": "ecommerce",
        "realism_level": "high"
      }
    }
  }'`;

const generateDataV2Prompt = `curl -X POST http://localhost:8001/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {
      "name": "generate_data",
      "arguments": {
        "rows": 200,
        "prompt": "Library system with books, authors, and checkouts",
        "realism_level": "medium"
      }
    }
  }'`;

const generateDataV2Response = `{
  "success": true,
  "data": {
    "entities": ["customers", "orders", "products"],
    "data": {
      "customers": [{ "id": "uuid-1", "email": "...", "name": "..." }, ...],
      "orders":    [{ "id": "uuid-2", "customer_id": "uuid-1", ... }, ...],
      "products":  [{ "id": "uuid-3", "name": "Widget Pro", ... }, ...]
    },
    "mode": "v2",
    "rows": 500,
    "fk_integrity": { "valid": true, "statistics": { "orders->customers": { ... } } },
    "metadata": {
      "semantic_analysis_summary": {
        "avg_confidence": 0.92, "total_fields": 12
      },
      "performance": { "total_ms": 12400 }
    }
  }
}`;

// ─── Tool overview cards ──────────────────────────────────────────────────────

const tools = [
  {
    icon: Wand2,
    title: "Prompt Refiner",
    version: "v0.10",
    playgroundTool: "refine_prompt",
    description: "Optimizes prompts with evidence-based stack detection and quality grounding",
    arguments: [
      { name: "prompt",               type: "string",   required: true  },
      { name: "domain",               type: "general|code|image|rag|llm", required: false },
      { name: "skill_level",          type: "string",   required: false },
      { name: "attached_files",       type: "string[]", required: false },
      { name: "project_files",        type: "object",   required: false },
      { name: "file_context",         type: "string",   required: false },
      { name: "conversation_history", type: "array",    required: false },
    ],
  },
  {
    icon: Database,
    title: "Data Generator",
    version: "v0.9",
    playgroundTool: "generate_data",
    description: "Generate realistic mock data in JSON or CSV format",
    arguments: [
      { name: "rows",          type: "number",      required: true  },
      { name: "format",        type: "json|csv",    required: true  },
      { name: "fields",        type: "string[]",    required: false },
      { name: "domain",        type: "string",      required: false },
      { name: "realism_level", type: "basic|medium|high", required: false },
    ],
  },
  {
    icon: FileCode,
    title: "Cheatsheet Generator",
    version: "v0.11",
    playgroundTool: null,
    description: "Generate curated code cheatsheets from YAML packs + LLM personalization",
    arguments: [
      { name: "language",    type: "string",                      required: true  },
      { name: "skill_level", type: "beginner|intermediate|expert", required: true  },
      { name: "intent",      type: "string",                      required: false },
    ],
  },
  {
    icon: Github,
    title: "GitHub Operations",
    version: "v1.0",
    playgroundTool: "github_operation",
    description: "26 structured ops — PR inspection, issue CRUD, releases, Actions, webhooks",
    arguments: [
      { name: "query",   type: "string", required: true  },
    ],
  },
  {
    icon: TestTube2,
    title: "Test Generator",
    version: "v1.0",
    playgroundTool: "generate_tests",
    description: "Generate ready-to-run unit tests with static validation — parse check + import guard",
    arguments: [
      { name: "code",             type: "string",                    required: true  },
      { name: "language",         type: "python|javascript|typescript", required: true  },
      { name: "framework",        type: "pytest|jest|vitest",         required: false },
      { name: "module_path",      type: "string",                    required: false },
      { name: "coverage",         type: "all|happy_path|edge_cases", required: false },
      { name: "use_repo_context", type: "boolean",                   required: false },
      { name: "instructions",     type: "string",                    required: false },
    ],
  },
];

// ─── Inline helpers ───────────────────────────────────────────────────────────

function CodeBlock({ code, className = "" }: { code: string; className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <pre className="bg-[#1A1815] text-[#E8E6DD] font-mono text-xs rounded-lg p-4 overflow-x-auto whitespace-pre">
        <code>{code}</code>
      </pre>
      <CopyButton text={code} />
    </div>
  );
}

function InlineCode({ children }: { children: string }) {
  return (
    <code className="bg-[rgb(var(--surface-2))] px-1.5 py-0.5 rounded text-xs font-mono">
      {children}
    </code>
  );
}

function ParamRow({
  name, type, required, description,
}: { name: string; type: string; required?: boolean; description: string }) {
  return (
    <tr className="border-b border-[rgb(var(--border))] last:border-0">
      <td className="py-2.5 pr-4 align-top">
        <InlineCode>{name}</InlineCode>
        {required && <span className="text-[rgb(var(--danger))] ml-1 text-xs">*</span>}
      </td>
      <td className="py-2.5 pr-4 align-top">
        <span className="text-xs font-mono text-[rgb(var(--accent))]">{type}</span>
      </td>
      <td className="py-2.5 text-xs text-[rgb(var(--text-muted))]">{description}</td>
    </tr>
  );
}

function CollapsibleSection({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
          <div className="text-sm text-[rgb(var(--text-muted))] mt-1">{subtitle}</div>
        </div>
        <button
          onClick={() => setOpen(s => !s)}
          className="flex items-center gap-1.5 shrink-0 text-xs font-medium border border-[rgb(var(--border))] rounded-lg px-3 py-1.5 text-[rgb(var(--accent))] hover:border-[rgb(var(--border-2))] transition-colors"
        >
          {open ? <Minus className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
          {open ? "Collapse" : "Show details"}
        </button>
      </div>
      {open && <div className="space-y-4">{children}</div>}
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocsPage() {
  return (
    <div className="space-y-10">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Documentation</h1>
        <p className="text-[rgb(var(--text-muted))] mt-1">Integrate with DevForge tools via MCP or REST</p>
      </div>

      {/* Quick start */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Quick Start</h2>
        <Card>
          <CardContent className="p-6 space-y-4">
            <div>
              <p className="text-sm font-medium mb-2">MCP / JSON-RPC 2.0 <Badge variant="default" className="text-xs ml-2">recommended</Badge></p>
              <p className="text-xs text-[rgb(var(--text-muted))] mb-3">
                Same protocol used by Cursor, Claude Desktop, and VS Code MCP extensions.
                <InlineCode>Accept: application/json, text/event-stream</InlineCode> is required even though responses are JSON.
              </p>
              <CodeBlock code={mcpQuickStart} />
            </div>
            <div className="border-t border-[rgb(var(--border))] pt-4">
              <p className="text-sm font-medium mb-2">REST <span className="text-xs text-[rgb(var(--text-muted))] font-normal">(legacy path)</span></p>
              <CodeBlock code={restQuickStart} />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Authentication */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Authentication</h2>
        <Card>
          <CardContent className="p-6 space-y-3">
            <p className="text-sm">
              All requests require an <InlineCode>x-api-key</InlineCode> header.
              Get your key from the <Link href="/dashboard/keys" className="text-[rgb(var(--accent))] hover:underline">API Keys</Link> page.
            </p>
            <CodeBlock code="x-api-key: df_your_key_here" />
            <p className="text-xs text-[rgb(var(--text-muted))]">
              Per-tier rate limits apply. Limit headers (<InlineCode>X-RateLimit-Limit-Hourly</InlineCode>, <InlineCode>X-RateLimit-Used-Hourly</InlineCode>, etc.)
              are returned on every <InlineCode>/mcp/</InlineCode> response.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Tool overview grid */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Available Tools</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tools.map((tool, i) => {
            const Icon = tool.icon;
            return (
              <Card key={i} className="hover:border-[rgb(var(--border-2))] transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="rounded-lg bg-[rgb(var(--accent-subtle))] p-2">
                        <Icon className="h-4 w-4 text-[rgb(var(--accent))]" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <CardTitle className="text-sm">{tool.title}</CardTitle>
                          <Badge variant="outline" className="text-[10px] font-mono">{tool.version}</Badge>
                        </div>
                        <CardDescription className="text-xs mt-0.5">{tool.description}</CardDescription>
                      </div>
                    </div>
                    {tool.playgroundTool && (
                      <Link href={`/dashboard/playground?tool=${tool.playgroundTool}`}>
                        <Button variant="outline" size="sm" className="gap-1.5 text-xs shrink-0">
                          <FlaskConical className="h-3.5 w-3.5" />
                          Try it
                        </Button>
                      </Link>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide mb-2">Parameters</p>
                  <div className="flex flex-wrap gap-1.5">
                    {tool.arguments.map((arg, j) => (
                      <Badge key={j} variant="outline" className="text-xs font-mono">
                        {arg.name}
                        <span className="ml-1 text-[rgb(var(--text-muted))] font-sans">({arg.type})</span>
                        {arg.required && <span className="ml-0.5 text-[rgb(var(--danger))]">*</span>}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* ── REFINE PROMPT DEEP DIVE ── */}
      <CollapsibleSection
        title="Prompt Refiner — Reference"
        subtitle={<>Tool name: <InlineCode>refine_prompt</InlineCode> · Version 0.10</>}
      >
        {/* Parameters */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgb(var(--border))]">
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Name</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Type</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                <ParamRow name="prompt"               type="string"   required description="The prompt to refine." />
                <ParamRow name="domain"               type="string"            description="Target domain. Options: general (default), code, image, rag, llm." />
                <ParamRow name="skill_level"          type="string"            description="Complexity target: beginner, intermediate (default), or expert." />
                <ParamRow name="attached_files"       type="string[]"          description="Array of code snippet strings. Parsed for imports and class names (weight 0.8)." />
                <ParamRow name="project_files"        type="object"            description='Dict of manifest filename → content, e.g. {"requirements.txt": "fastapi==0.100.0"}. Highest-weight evidence (0.9).' />
                <ParamRow name="file_context"         type="string"            description="Free-form context string appended to the refinement prompt." />
                <ParamRow name="conversation_history" type="array"             description='Array of {role, content} message objects. Soft evidence source (weight 0.4).' />
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Domain guide */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Domains</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              {[
                { d: "general", desc: "Default. Works for any prompt — no stack analysis." },
                { d: "code",    desc: "Analyzes attached_files and project_files for stack evidence. When confidence ≥ 0.6, injects an EVIDENCE block into the LLM prompt that enforces detected frameworks — prevents hallucination." },
                { d: "image",   desc: "Optimizes for image generation (composition, style, lighting, negative prompts)." },
                { d: "rag",     desc: "Tailored for retrieval-augmented generation pipelines (chunking, retrieval strategy hints)." },
                { d: "llm",     desc: "System-prompt optimization for LLM applications." },
              ].map(({ d, desc }) => (
                <div key={d} className="flex gap-3">
                  <InlineCode>{d}</InlineCode>
                  <p className="text-[rgb(var(--text-muted))] flex-1">{desc}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Supported manifests */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Supported <InlineCode>project_files</InlineCode> Manifests</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Pass these as keys in <InlineCode>project_files</InlineCode>. Each is parsed by a dedicated parser — unrecognised packages are silently skipped.
            </p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
              {[
                ["requirements.txt", "Python (FastAPI, Django, Flask…)"],
                ["package.json",     "JS / Node (React, Next.js, Vue…)"],
                ["go.mod",           "Go (Gin, Echo, Fiber…)"],
                ["Cargo.toml",       "Rust (Actix, Axum, Rocket…)"],
                ["pom.xml",          "Java (Spring Boot, Hibernate…)"],
                ["Gemfile",          "Ruby (Rails, Sinatra…)"],
                ["composer.json",    "PHP (Laravel, Symfony…)"],
                ["build.gradle",     "Java / Kotlin (Spring Boot, Ktor…)"],
              ].map(([file, desc]) => (
                <div key={file} className="flex items-start gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-[rgb(var(--success))] mt-0.5 shrink-0" />
                  <div>
                    <span className="font-mono text-[rgb(var(--text))]">{file}</span>
                    <span className="text-[rgb(var(--text-muted))] ml-2">{desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Examples */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — Basic</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Minimal call. Quality grounding will be <span className="text-[rgb(var(--danger))] font-medium">low</span> — the tool returns <InlineCode>suggested_inputs</InlineCode> pointing you to add context.
            </p>
          </CardHeader>
          <CardContent>
            <CodeBlock code={refineBasic} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — With Code Context</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Providing <InlineCode>project_files</InlineCode> (0.9 weight) and <InlineCode>attached_files</InlineCode> (0.8 weight) raises grounding to <span className="text-yellow-500 font-medium">medium</span> or <span className="text-[rgb(var(--success))] font-medium">high</span> and enables the EVIDENCE block — the LLM must use detected frameworks.
            </p>
          </CardHeader>
          <CardContent>
            <CodeBlock code={refineWithContext} />
          </CardContent>
        </Card>

        {/* Quality grounding */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Quality Grounding (<InlineCode>data.quality</InlineCode>)</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Returned on every call. Use <InlineCode>prompt_grounding</InlineCode> to decide whether to re-call with more context.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2 text-xs">
              {[
                {
                  level: "high",
                  color: "text-[rgb(var(--success))]",
                  border: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)]",
                  desc: "Strong evidence — project_files + attached_files present with confident stack match. LLM receives an EVIDENCE block; hallucination risk is minimal.",
                },
                {
                  level: "medium",
                  color: "text-yellow-500",
                  border: "border-yellow-500/30 bg-yellow-500/5",
                  desc: "Partial evidence — one strong signal present but some signals (e.g. database) still missing. missing_signals lists what would raise confidence further.",
                },
                {
                  level: "low",
                  color: "text-[rgb(var(--danger))]",
                  border: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)]",
                  desc: "Vague input — no files, no manifest. The tool still refines the prompt but cannot ground stack choices. Check suggested_inputs and re-call with more context.",
                },
              ].map(({ level, color, border, desc }) => (
                <div key={level} className={`flex gap-3 rounded-lg border px-3 py-2.5 ${border}`}>
                  <span className={`font-bold uppercase tracking-wider w-14 shrink-0 ${color}`}>{level}</span>
                  <p className="text-[rgb(var(--text-muted))]">{desc}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              <strong className="text-[rgb(var(--text))]">Iterative pattern:</strong>{" "}
              if <InlineCode>prompt_grounding === &quot;low&quot;</InlineCode>, read <InlineCode>quality.suggested_inputs</InlineCode> and re-call with the listed fields populated.
            </p>
          </CardContent>
        </Card>

        {/* Response shape */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Response Shape</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Gateway (<InlineCode>/api/gateway</InlineCode>) returns this directly. MCP (<InlineCode>/mcp/</InlineCode>) wraps it in <InlineCode>result.structuredContent</InlineCode>.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium mb-2">Tool data (<InlineCode>result.structuredContent</InlineCode> via MCP / top-level via gateway)</p>
              <CodeBlock code={refineResponse} />
            </div>
            <div>
              <p className="text-xs font-medium mb-2">MCP JSON-RPC envelope</p>
              <CodeBlock code={mcpResponseShape} />
            </div>
            <div className="text-xs space-y-1.5 pt-1">
              <p className="font-medium text-[rgb(var(--text))]">Response fields</p>
              {[
                ["refined_prompt",    "string",  "The optimized prompt."],
                ["context_summary",   "string",  "Human-readable summary of detected stack and code context."],
                ["chosen_stack",      "object",  "languages, frameworks, libraries, services, databases (all string[]), plus confidence (0–1) and evidence array."],
                ["chosen_stack.evidence", "array", "Each item: match, source, file, line, excerpt, weight (0–1), confidence_hint."],
                ["quality",           "object",  "prompt_grounding (low|medium|high), missing_signals[], suggested_inputs[]."],
                ["sanitization_log",  "array",   "Metadata for any redacted secrets or blocked injections. Values are never logged."],
                ["execution_time",    "number",  "Wall-clock seconds. Code domain with full evidence: 9–16 s on shared free LLM endpoint."],
              ].map(([field, type, desc]) => (
                <div key={field} className="grid grid-cols-[180px_80px_1fr] gap-3 text-[rgb(var(--text-muted))]">
                  <InlineCode>{field}</InlineCode>
                  <span className="font-mono text-[rgb(var(--accent))] text-[10px] pt-0.5">{type}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Performance note */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
              {[
                ["general / image / rag domain, no context", "2 – 4 s"],
                ["code domain, no evidence",                 "4 – 7 s"],
                ["code domain, full evidence",               "9 – 16 s"],
                ["injection blocked (no LLM call)",          "1 – 2 s"],
              ].map(([scenario, time]) => (
                <div key={scenario} className="flex justify-between border-b border-[rgb(var(--border))] py-1.5 col-span-1">
                  <span className="text-[rgb(var(--text-muted))]">{scenario}</span>
                  <span className="font-mono text-[rgb(var(--text))] ml-4 shrink-0">{time}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-3">
              Latency is dominated by the shared free LLM endpoint. Self-hosting Ollama or pointing <InlineCode>OLLAMA_HOST</InlineCode> at a paid provider brings code-domain calls under 3 s.
            </p>
          </CardContent>
        </Card>
      </CollapsibleSection>

      {/* ── GENERATE TESTS DEEP DIVE ── */}
      <CollapsibleSection
        title="Test Generator — Reference"
        subtitle={<>Tool name: <InlineCode>generate_tests</InlineCode> · Version 1.0</>}
      >
        {/* Parameters */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgb(var(--border))]">
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Name</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Type</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                <ParamRow name="code"             type="string"   required description="Source under test, verbatim. Max 16 000 chars." />
                <ParamRow name="language"         type="string"   required description="python, javascript, or typescript. Anything else is rejected." />
                <ParamRow name="framework"        type="string"            description="pytest, jest, or vitest. Defaults: py→pytest, js/ts→jest. Invalid combos (e.g. python+jest) return success:false." />
                <ParamRow name="module_path"      type="string"            description="Import hint, e.g. src.utils.auth (Python) or ../src/auth (JS/TS). Strongly recommended — omitting adds a placeholder warning." />
                <ParamRow name="coverage"         type="string"            description="all (default), happy_path, or edge_cases. Steers which scenarios the LLM targets." />
                <ParamRow name="use_repo_context" type="boolean"           description="When true, related snippets from the tenant's indexed repo enrich the prompt. Best-effort: no-op when nothing is indexed." />
                <ParamRow name="instructions"     type="string"            description="Free-form 1-line steer, e.g. focus on error paths. Max 1 000 chars." />
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* validated semantics */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Validation Levels (<InlineCode>data.validated</InlineCode>)</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              The tool reports exactly what guarantee you got — it never silently drops bad output.
            </p>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              {
                level: "static",
                color: "text-[rgb(var(--success))]",
                border: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)]",
                desc: "Parse OK + all imports from the source module resolve. unresolved_symbols is empty. Safe to run.",
              },
              {
                level: "partial",
                color: "text-yellow-500",
                border: "border-yellow-500/30 bg-yellow-500/5",
                desc: "Parse OK but some names imported from the module don't exist in the pasted source. unresolved_symbols lists the bad names — review before running.",
              },
              {
                level: "unparseable",
                color: "text-[rgb(var(--danger))]",
                border: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)]",
                desc: "Two generation attempts produced syntactically invalid code. Best-effort output returned; cases[] may be empty. A warning is included.",
              },
            ].map(({ level, color, border, desc }) => (
              <div key={level} className={`flex gap-3 rounded-lg border px-3 py-2.5 text-xs ${border}`}>
                <span className={`font-bold uppercase tracking-wider w-24 shrink-0 ${color}`}>{level}</span>
                <p className="text-[rgb(var(--text-muted))]">{desc}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Examples */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — Python / pytest</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Minimal call. <InlineCode>module_path</InlineCode> is strongly recommended — omitting it adds a placeholder warning to the response.
            </p>
          </CardHeader>
          <CardContent>
            <CodeBlock code={generateTestsPython} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — TypeScript / Vitest with targeted coverage</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              <InlineCode>coverage: &quot;edge_cases&quot;</InlineCode> steers the LLM to focus on error paths. <InlineCode>instructions</InlineCode> adds an extra nudge.
            </p>
          </CardHeader>
          <CardContent>
            <CodeBlock code={generateTestsTypescript} />
          </CardContent>
        </Card>

        {/* Response shape */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Response Shape</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock code={generateTestsResponse} />
            <div className="text-xs space-y-1.5 pt-1">
              <p className="font-medium text-[rgb(var(--text))]">Response fields</p>
              {[
                ["filename",           "string",   "Suggested save path (test_calc.py, auth.test.ts, …). IDE can save in one click."],
                ["test_file",          "string",   "Full generated source. Ready to paste into your repo."],
                ["cases",              "array",    "Each item: { name, asserts }. name is always accurate; asserts may be empty for pytest.raises or expect(...).toBe(...) tests."],
                ["validated",          "string",   "static | partial | unparseable — see table above."],
                ["unresolved_symbols", "string[]", "Imports from the module that don't exist in the pasted source. Empty when validated == \"static\"."],
                ["warnings",           "string[]", "Human-readable notes: placeholder import path, validation gaps, etc."],
                ["repo_context_used",  "boolean",  "true iff use_repo_context was set and RAG returned at least one snippet."],
                ["tokens_used",        "number",   "Total LLM tokens consumed (sum across attempts)."],
              ].map(([field, type, desc]) => (
                <div key={field} className="grid grid-cols-[160px_80px_1fr] gap-3 text-[rgb(var(--text-muted))]">
                  <InlineCode>{field}</InlineCode>
                  <span className="font-mono text-[rgb(var(--accent))] text-[10px] pt-0.5">{type}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Failure modes */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Failure Modes</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[rgb(var(--border))]">
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium w-[45%]">Condition</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 font-medium">Response</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["code empty or > 16 000 chars",               "success:false (Pydantic validation)"],
                  ["Unsupported language (e.g. ruby)",            "success:false"],
                  ["Invalid framework/language combo (py + jest)","success:false with message"],
                  ["No def / class in source",                    "success:false — \"no top-level functions or classes found\""],
                  ["LLM returns unparseable text twice",          "success:true, validated:\"unparseable\", warning included"],
                  ["LLM imports a symbol that doesn't exist",     "success:true, validated:\"partial\", unresolved_symbols populated"],
                  ["RAG requested but no repo indexed",           "repo_context_used:false, no warning (silent)"],
                  ["Ollama / model error",                        "success:false, data.message carries the error"],
                ].map(([cond, res]) => (
                  <tr key={cond} className="border-b border-[rgb(var(--border))] last:border-0">
                    <td className="py-2 pr-4 text-[rgb(var(--text-muted))]">{cond}</td>
                    <td className="py-2 font-mono text-[rgb(var(--text))]">{res}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Performance */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
              {[
                ["Single attempt (no retry)",   "5 – 20 s"],
                ["With one retry (worst case)", "~2× single call"],
              ].map(([scenario, time]) => (
                <div key={scenario} className="flex justify-between border-b border-[rgb(var(--border))] py-1.5 col-span-1">
                  <span className="text-[rgb(var(--text-muted))]">{scenario}</span>
                  <span className="font-mono text-[rgb(var(--text))] ml-4 shrink-0">{time}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-3">
              Latency is dominated by the cloud <InlineCode>code_gen</InlineCode> model (<InlineCode>qwen3-coder:480b-cloud</InlineCode> with fallback).
              The tool makes at most one retry — parse or import failure on the first attempt triggers a corrective second call.
            </p>
          </CardContent>
        </Card>
      </CollapsibleSection>

      {/* ── DATA GENERATOR DEEP DIVE ── */}
      <CollapsibleSection
        title="Data Generator — Reference"
        subtitle={<>Tool name: <InlineCode>generate_data</InlineCode> · Version 0.9 · V1 fast path + V2 multi-entity relational</>}
      >
        {/* Latency warning — prominent */}
        <Card>
          <CardContent className="p-4">
            <div className="rounded-lg border border-[rgb(var(--warning)/0.3)] bg-[rgb(var(--warning)/0.06)] px-4 py-3 text-sm">
              <p className="font-semibold text-[rgb(var(--warning))] mb-1">V2 latency: 1–4 minutes cold, 5–10 s warm</p>
              <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">
                V2 makes multiple LLM calls: schema design (~5 s) + one catalog generation call per entity (~3–4 s each).
                A 3-entity domain = ~4 LLM calls on cold cache. Warm cache (L2, 1h TTL, same prompt) cuts that to 5–10 s.
                V1 (no <InlineCode>domain</InlineCode> or <InlineCode>prompt</InlineCode>) is Faker-only and takes &lt;1 s.
                The Playground shows a wait message; long-running integrations should subscribe to the <InlineCode>progress_callback</InlineCode> stream.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Mode selection */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Mode Selection</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              The tool auto-selects based on which inputs you provide.
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-xs">
              {[
                { mode: "V1 — Faker fast path", trigger: "Neither domain nor prompt provided", example: "rows + fields only", note: "< 1 s. Single flat table." },
                { mode: "V2 — domain template", trigger: "domain provided", example: "ecommerce / saas / iot_devices", note: "9–17 s cold. Pre-built multi-entity schema." },
                { mode: "V2 — LLM schema design", trigger: "prompt provided", example: "Any free-text description", note: "15–30 s cold. LLM designs the schema." },
              ].map(({ mode, trigger, example, note }) => (
                <div key={mode} className="rounded-lg border border-[rgb(var(--border))] px-3 py-2.5 grid grid-cols-[140px_1fr_1fr] gap-3">
                  <span className="font-semibold text-[rgb(var(--text))]">{mode}</span>
                  <span className="text-[rgb(var(--text-muted))]">trigger: <InlineCode>{trigger}</InlineCode></span>
                  <span className="text-[rgb(var(--text-muted))]">{note}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Parameters */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgb(var(--border))]">
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Name</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 pr-4 font-medium">Type</th>
                  <th className="text-left text-[10px] uppercase tracking-wide text-[rgb(var(--text-muted))] pb-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                <ParamRow name="rows"   type="integer" required description="Rows to generate. 1–10 000 (Pydantic gate). V2 counts are distributed across entities." />
                <ParamRow name="format" type="string"           description="json (default) or csv." />
                <ParamRow name="prompt" type="string"           description="V2 only. Free-text schema description. LLM designs entities, fields, and relationships." />
                <ParamRow name="domain" type="string"           description="V2 only. ecommerce, saas, or iot_devices. Faster than prompt (no schema-design LLM call)." />
                <ParamRow name="fields" type="string[]"         description="V1 only. Custom field names to generate (Faker-based). Ignored when domain or prompt is set." />
                <ParamRow name="realism_level" type="string"   description="V2 only. basic (default) · medium (~5% nulls) · high (10% nulls + 2% duplicates + 1% outliers)." />
                <ParamRow name="enable_semantic_generation" type="boolean" description="V2 only. Default true. Enables context-aware value generation (flower.name → actual flower names)." />
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Domain templates */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Domain Templates</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Pass <InlineCode>domain</InlineCode> for pre-built multi-entity schemas with enforced foreign keys.
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-xs">
              {[
                { d: "ecommerce",   entities: "customers · orders · products",             note: "orders→customers (1:N), orders→products (1:N)" },
                { d: "saas",        entities: "users · subscriptions · usage_logs",        note: "subscriptions→users (1:N), usage_logs→subscriptions (1:N)" },
                { d: "iot_devices", entities: "devices · readings",                        note: "readings→devices (1:N)" },
              ].map(({ d, entities, note }) => (
                <div key={d} className="rounded-lg border border-[rgb(var(--border))] px-3 py-2.5">
                  <div className="flex items-center gap-3 mb-1">
                    <InlineCode>{d}</InlineCode>
                    <span className="text-[rgb(var(--text-muted))]">{entities}</span>
                  </div>
                  <p className="text-[rgb(var(--text-muted))] pl-0">{note}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Realism levels */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Realism Levels</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Applied after generation. Critical fields (<InlineCode>id</InlineCode>, <InlineCode>email</InlineCode>, <InlineCode>created_at</InlineCode>, FKs) are never nulled.
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-xs">
              {[
                { level: "basic",  color: "text-[rgb(var(--success))]",  border: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)]",   desc: "0% nulls, 0% duplicates, 0% outliers. All data clean and consistent." },
                { level: "medium", color: "text-yellow-500",              border: "border-yellow-500/30 bg-yellow-500/5",                              desc: "~5% nulls on nullable fields (phone, address, last_login, etc.)." },
                { level: "high",   color: "text-[rgb(var(--danger))]",   border: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)]",      desc: "~10% nulls + ~2% duplicate rows + ~1% numeric outliers. Tests real-world data quality handling." },
              ].map(({ level, color, border, desc }) => (
                <div key={level} className={`flex gap-3 rounded-lg border px-3 py-2.5 ${border}`}>
                  <span className={`font-bold uppercase tracking-wider w-14 shrink-0 ${color}`}>{level}</span>
                  <p className="text-[rgb(var(--text-muted))]">{desc}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Examples */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — V1 (fast, Faker-based)</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              No <InlineCode>domain</InlineCode> or <InlineCode>prompt</InlineCode> → V1 mode. Completes in &lt;1 s.
            </p>
          </CardHeader>
          <CardContent><CodeBlock code={generateDataV1} /></CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — V2 domain template (ecommerce)</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Uses pre-built schema — no schema-design LLM call. 9–17 s cold, 5–10 s warm.
            </p>
          </CardHeader>
          <CardContent><CodeBlock code={generateDataV2Domain} /></CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Example — V2 prompt (LLM schema design)</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              LLM designs a custom schema from the description. 15–30 s cold.
            </p>
          </CardHeader>
          <CardContent><CodeBlock code={generateDataV2Prompt} /></CardContent>
        </Card>

        {/* Response shape */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">V2 Response Shape</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              V1 returns a flat <InlineCode>data.data</InlineCode> JSON string. V2 returns a structured multi-entity object.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock code={generateDataV2Response} />
            <div className="text-xs space-y-1.5 pt-1">
              <p className="font-medium text-[rgb(var(--text))]">Key response fields</p>
              {[
                ["data.entities",       "string[]", "Ordered list of entity names."],
                ["data.data",           "object",   "Map of entity name → rows array."],
                ["data.fk_integrity",   "object",   "valid: bool + per-relationship statistics (orphaned_children, parents_with_zero_children, …)."],
                ["data.metadata.semantic_analysis_summary", "object", "avg_confidence, total_fields, classified_by_* counts."],
                ["data.constraint_violations", "array", "Any schema constraint breaches (enum/pattern/range). Non-empty → success: false."],
                ["data.mode",           "string",   "v1 or v2."],
              ].map(([field, type, desc]) => (
                <div key={field} className="grid grid-cols-[200px_70px_1fr] gap-3 text-[rgb(var(--text-muted))]">
                  <InlineCode>{field}</InlineCode>
                  <span className="font-mono text-[rgb(var(--accent))] text-[10px] pt-0.5">{type}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Performance */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Performance Reference</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs">
              {[
                ["V1 — any row count",                     "< 1 s"],
                ["V2 domain — cold cache",                 "9 – 17 s"],
                ["V2 domain — warm cache (1h TTL)",        "5 – 10 s"],
                ["V2 prompt — cold cache (3-entity)",      "15 – 30 s"],
                ["V2 prompt — warm cache",                 "5 – 10 s"],
                ["V2 ecommerce 2 000 rows, realism=high",  "~45 s"],
              ].map(([scenario, time]) => (
                <div key={scenario} className="flex justify-between border-b border-[rgb(var(--border))] py-1.5">
                  <span className="text-[rgb(var(--text-muted))]">{scenario}</span>
                  <span className="font-mono text-[rgb(var(--text))] ml-4 shrink-0">{time}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-3">
              Cache key: <InlineCode>entity + fields_hash + prompt_hash</InlineCode>. The same domain call within 1h reuses cached catalogs and skips per-entity LLM calls.
            </p>
          </CardContent>
        </Card>
      </CollapsibleSection>

      {/* ── GITHUB OPERATIONS DEEP DIVE ── */}
      <CollapsibleSection
        title="GitHub Operations — Reference"
        subtitle={<>Tool name: <InlineCode>github_operation</InlineCode> · Version 1.0 · 26 structured ops</>}
      >
        {/* PAT token */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Authentication — GitHub PAT</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Every call needs a GitHub Personal Access Token. Pass it per-request in <InlineCode>context.github_token</InlineCode>.
              The server-level <InlineCode>GITHUB_TOKEN</InlineCode> env var is a fallback only.
            </p>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="rounded-lg border border-[rgb(var(--border))] divide-y">
              {[
                ["context.github_token", "string", "Per-request PAT. Canonical path. Takes precedence over server env var."],
                ["context.risk_confirmed", "boolean", "Required for HIGH ops (create_repo, delete_branch, create_release, …). Set to true."],
                ["context.risk_reason", "string", "Required for CRITICAL ops (delete_repo, merge into production). Non-empty string."],
                ["context.session_id", "string", "From a previous disambiguation response. Re-submits with a chosen repo."],
              ].map(([field, type, desc]) => (
                <div key={field} className="grid grid-cols-[200px_70px_1fr] gap-3 px-3 py-2 text-[rgb(var(--text-muted))]">
                  <InlineCode>{field}</InlineCode>
                  <span className="font-mono text-[rgb(var(--accent))] text-[10px] pt-0.5">{type}</span>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
            <p className="text-[rgb(var(--text-muted))]">
              In the Playground, the <strong className="text-[rgb(var(--text))]">GitHub PAT</strong> field is saved locally and injected automatically.
              Required PAT scopes: <InlineCode>repo</InlineCode> for most ops; <InlineCode>delete_repo</InlineCode> for repo deletion; <InlineCode>write:repo_hook</InlineCode> for webhooks; <InlineCode>workflow</InlineCode> for Actions.
            </p>
          </CardContent>
        </Card>

        {/* NL mode */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Natural Language Mode — both endpoints</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Send a plain English <InlineCode>query</InlineCode>. Works on both <InlineCode>/mcp/</InlineCode> and <InlineCode>/api/gateway</InlineCode>.
              The LLM extracts intent, fuzzy-matches the repo name, and routes to the right operation.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium mb-2">MCP / JSON-RPC 2.0</p>
              <CodeBlock code={githubNlListRepos} />
            </div>
            <div className="border-t border-[rgb(var(--border))] pt-4">
              <p className="text-xs font-medium mb-2">REST gateway</p>
              <CodeBlock code={githubGatewayNl} />
            </div>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              The REST gateway accepts <strong>NL only</strong>. Structured mode (<InlineCode>operation</InlineCode> key) is MCP-only.
            </p>
          </CardContent>
        </Card>

        {/* Structured mode */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Structured Mode — MCP only</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Pass <InlineCode>operation</InlineCode> + flat params directly — no LLM classification.
              Faster and deterministic. Parameters go <strong>flat</strong>, not nested under <InlineCode>parameters</InlineCode>.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock code={githubStructuredCreateIssue} />
            <p className="text-xs text-[rgb(var(--text-muted))]">
              26 supported operations: <InlineCode>list_repos</InlineCode>, <InlineCode>browse_files</InlineCode>, <InlineCode>read_file</InlineCode>, <InlineCode>search_code</InlineCode>, <InlineCode>list_branches</InlineCode>, <InlineCode>list_pull_requests</InlineCode>, <InlineCode>get_pr</InlineCode>, <InlineCode>list_commits</InlineCode>, <InlineCode>get_commit</InlineCode>, <InlineCode>list_releases</InlineCode>, <InlineCode>list_webhooks</InlineCode>, <InlineCode>create_issue</InlineCode>, <InlineCode>add_comment</InlineCode>, <InlineCode>update_issue</InlineCode>, <InlineCode>close_issue</InlineCode>, <InlineCode>commit_file</InlineCode>, <InlineCode>create_branch</InlineCode>, <InlineCode>create_pull_request</InlineCode>, <InlineCode>merge_pr</InlineCode>, <InlineCode>create_repo</InlineCode>, <InlineCode>delete_branch</InlineCode>, <InlineCode>create_release</InlineCode>, <InlineCode>trigger_workflow</InlineCode>, <InlineCode>create_webhook</InlineCode>, <InlineCode>delete_webhook</InlineCode>, <InlineCode>delete_repo</InlineCode>.
            </p>
          </CardContent>
        </Card>

        {/* Risk gate */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Risk Gate</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              Every operation has a base risk level. Some escalate contextually based on target branch or parameter values.
            </p>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            {[
              {
                level: "LOW",
                color: "text-[rgb(var(--success))]",
                border: "border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.06)]",
                req: "None",
                examples: "list_repos, browse_files, read_file, search_code, list_branches, add_comment",
              },
              {
                level: "MEDIUM",
                color: "text-[rgb(var(--accent))]",
                border: "border-[rgb(var(--accent)/0.3)] bg-[rgb(var(--accent)/0.06)]",
                req: "None",
                examples: "create_issue, commit_file, create_branch, create_pull_request, merge_pr (feature branch)",
              },
              {
                level: "HIGH",
                color: "text-yellow-500",
                border: "border-yellow-500/30 bg-yellow-500/5",
                req: "context.risk_confirmed: true",
                examples: "create_repo, delete_branch, create_release, trigger_workflow, create_webhook, delete_webhook",
              },
              {
                level: "CRITICAL",
                color: "text-[rgb(var(--danger))]",
                border: "border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.06)]",
                req: "risk_confirmed: true + risk_reason: \"…\"",
                examples: "delete_repo, merge_pr into production, delete_branch=main",
              },
            ].map(({ level, color, border, req, examples }) => (
              <div key={level} className={`rounded-lg border px-3 py-2.5 ${border}`}>
                <div className="flex items-center gap-3 mb-1">
                  <span className={`font-bold uppercase tracking-wider w-16 shrink-0 ${color}`}>{level}</span>
                  <InlineCode>{req}</InlineCode>
                </div>
                <p className="text-[rgb(var(--text-muted))] pl-0">{examples}</p>
              </div>
            ))}
            <div className="space-y-1 pt-1">
              <p className="font-medium text-[rgb(var(--text))]">Contextual escalation</p>
              <div className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[rgb(var(--text-muted))]">
                <span><InlineCode>merge_pr</InlineCode> into main/master</span><span className="font-mono text-yellow-500">→ HIGH</span>
                <span><InlineCode>merge_pr</InlineCode> into production/release/*</span><span className="font-mono text-[rgb(var(--danger))]">→ CRITICAL</span>
                <span><InlineCode>delete_branch</InlineCode> = main/master/production</span><span className="font-mono text-[rgb(var(--danger))]">→ CRITICAL</span>
                <span><InlineCode>commit_file</InlineCode> to main/master/production</span><span className="font-mono text-yellow-500">→ HIGH</span>
                <span><InlineCode>create_release</InlineCode> with prerelease: true</span><span className="font-mono text-[rgb(var(--accent))]">↓ MEDIUM</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* HIGH + CRITICAL examples */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">HIGH op — <InlineCode>create_repo</InlineCode></CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock code={githubHighOpExample} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">CRITICAL op — <InlineCode>delete_repo</InlineCode></CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock code={githubCriticalOpExample} />
          </CardContent>
        </Card>

        {/* Error enrichment */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Error Enrichment</CardTitle>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
              GitHub 403/404/422 errors are enriched with actionable guidance rather than raw API messages.
            </p>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {[
              ["403 — Permission denied", "Lists the missing PAT scopes + link to generate a new token. E.g. create_webhook needs write:repo_hook."],
              ["404 — Not found", "Reminds you to use owner/repo format. Also surfaces when a branch or PR doesn't exist."],
              ["422 — Validation error", "Passes through GitHub's message, e.g. \"Reference already exists\" for duplicate branch creation."],
              ["Risk gate block", "HTTP 200 success:false via gateway; JSON-RPC -32603 error via MCP. Gateway path includes audit_id and timeline."],
              ["Disambiguation", "Multiple repos match the query → success:false with status:needs_clarification and an options[] array. Re-call with context.session_id + context.selected_repo."],
            ].map(([condition, desc]) => (
              <div key={condition} className="border-b border-[rgb(var(--border))] pb-2 last:border-0 last:pb-0">
                <p className="font-medium text-[rgb(var(--text))] mb-0.5">{condition}</p>
                <p className="text-[rgb(var(--text-muted))]">{desc}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </CollapsibleSection>

      {/* MCP Integration */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">MCP Integration</h2>
        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="text-sm">
              Add DevForge to Cursor, Claude Desktop, or any MCP-compatible IDE.
              The trailing slash on the URL is mandatory.
            </p>
            <CodeBlock code={mcpConfig} />
            <ul className="text-xs text-[rgb(var(--text-muted))] space-y-1.5 pt-1">
              <li>• No <InlineCode>initialize</InlineCode> handshake needed — the server runs in stateless HTTP mode.</li>
              <li>• No SSE streaming — every response is a regular JSON body.</li>
              <li>• Tool list is live: <InlineCode>POST /mcp/</InlineCode> with <InlineCode>&quot;method&quot;: &quot;tools/list&quot;</InlineCode> returns current tool schemas.</li>
            </ul>
          </CardContent>
        </Card>
      </section>

      {/* Response format (error handling) */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">Error Handling</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-[rgb(var(--success))]">Success (MCP)</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock code={`{\n  "result": {\n    "structuredContent": { "success": true, ... },\n    "isError": false\n  }\n}`} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-[rgb(var(--danger))]">Transport Error (MCP)</CardTitle>
              <p className="text-xs text-[rgb(var(--text-muted))] mt-1">Rate limit, schema rejection, or auth failure</p>
            </CardHeader>
            <CardContent>
              <CodeBlock code={`{\n  "error": {\n    "code": -32000,\n    "message": "Rate limit exceeded",\n    "data": { "limit_info": { ... } }\n  }\n}`} />
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
