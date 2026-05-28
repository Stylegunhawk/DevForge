import Link from "next/link";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Wand2, TestTube2, Database, Github, FileCode,
  ArrowRight, Check, Zap,
} from "lucide-react";

// ── Tool catalogue ────────────────────────────────────────────────────────────

const tools = [
  {
    icon: Wand2,
    name: "Prompt Refiner",
    slug: "refine_prompt",
    version: "v0.10",
    description:
      "Evidence-based stack detection refines vague prompts into grounded, hallucination-resistant instructions with a deterministic quality signal.",
    tags: null,
  },
  {
    icon: TestTube2,
    name: "Test Generator",
    slug: "generate_tests",
    version: "v1.0",
    description:
      "Produces ready-to-run pytest / Jest / Vitest files with tree-sitter parse validation and an import-symbol guard — no hallucinated APIs.",
    tags: null,
  },
  {
    icon: Database,
    name: "Data Generator",
    slug: "generate_data",
    version: "v0.9",
    description:
      "Realistic JSON or CSV mock data with per-entity LLM catalog caching and three configurable realism levels.",
    tags: null,
  },
  {
    icon: Github,
    name: "GitHub Operations",
    slug: "github_operation",
    version: "v1.0",
    description:
      "26 structured ops — PRs, issues, releases, webhooks, Actions — via natural language or deterministic structured calls with a multi-layer risk gate.",
    tags: null,
  },
  {
    icon: FileCode,
    name: "Cheatsheet Generator",
    slug: null,
    version: "v0.11",
    description:
      "Curated YAML packs + LLM personalization across 9 languages. Every snippet is tree-sitter syntax-validated in CI.",
    tags: ["python", "typescript", "go", "rust", "java", "+4"],
  },
];

// ── Dark pill (used inside always-dark sections) ──────────────────────────────

function DarkPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="px-3 py-1 rounded-full border border-[#2E2B26] text-xs text-[#6B6860] bg-[#21201B]">
      {children}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] text-[rgb(var(--text))]">

      {/* ═══════════════════════════════════ NAV ══════════════════════════════════ */}
      <header className="sticky top-0 z-50 border-b border-[rgb(var(--border))] bg-[rgb(var(--bg))] backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-8">
          <Link href="/" className="shrink-0">
            <Logo size="sm" />
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-sm text-[rgb(var(--text-muted))]">
            <a href="#tools" className="hover:text-[rgb(var(--text))] transition-colors">Tools</a>
            <a href="#integration" className="hover:text-[rgb(var(--text))] transition-colors">Integration</a>
            <Link href="/dashboard/docs" className="hover:text-[rgb(var(--text))] transition-colors">Docs</Link>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/login"
              className="hidden sm:inline-flex items-center px-4 py-1.5 rounded-lg text-sm font-medium text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))] hover:bg-[rgb(var(--surface-2))] transition-colors"
            >
              Sign in
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-hover))] transition-colors"
            >
              Get started
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ══════════════════════════════════ HERO ══════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24 lg:pt-28 lg:pb-32 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-14 lg:gap-20 items-center">

        {/* ── Left column ── */}
        <div>
          {/* Eyebrow badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[rgb(var(--accent)/0.25)] bg-[rgb(var(--accent-subtle))] text-[rgb(var(--accent))] text-xs font-semibold mb-8 select-none">
            <Zap className="h-3 w-3" />
            MCP · REST · Static validation
          </div>

          {/* Headline */}
          <h1 className="text-[2.75rem] lg:text-[3.25rem] font-bold tracking-tight leading-[1.1] mb-6">
            Developer tools<br />
            that{" "}
            <span className="text-[rgb(var(--accent))]">know</span>{" "}
            your stack.
          </h1>

          {/* Body */}
          <p className="text-lg text-[rgb(var(--text-muted))] leading-relaxed max-w-[440px] mb-10">
            Five AI tools — test generation, prompt refinement, GitHub automation,
            and more — served from one MCP server or REST endpoint.
            Connect once. Use from any IDE.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-3 mb-10">
            <Link
              href="/register"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-hover))] transition-colors"
              style={{ boxShadow: "0 2px 16px rgba(217,119,87,0.25)" }}
            >
              Get started free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold border border-[rgb(var(--border-2))] text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))] hover:border-[rgb(var(--accent)/0.35)] transition-colors"
            >
              Sign in
            </Link>
          </div>

          {/* Proof chips */}
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-[rgb(var(--text-muted))]">
            {[
              "5 AI tools",
              "MCP + REST",
              "No hallucinated APIs",
              "64 / 64 live tests passing",
            ].map(item => (
              <span key={item} className="flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-[rgb(var(--success))]" />
                {item}
              </span>
            ))}
          </div>
        </div>

        {/* ── Right column — Terminal card ── */}
        <div className="relative">
          {/* Ambient glow */}
          <div
            className="absolute inset-0 rounded-3xl -z-10 blur-3xl scale-110"
            style={{ background: "rgba(217,119,87,0.07)" }}
          />

          <div
            className="rounded-2xl overflow-hidden border border-[#2E2B26]"
            style={{ background: "#141210", boxShadow: "0 24px 64px rgba(0,0,0,0.35)" }}
          >
            {/* Window chrome */}
            <div className="flex items-center gap-1.5 px-4 py-3 border-b border-[#2E2B26]">
              <div className="h-3 w-3 rounded-full bg-[#FF5F56]" />
              <div className="h-3 w-3 rounded-full bg-[#FFBD2E]" />
              <div className="h-3 w-3 rounded-full bg-[#27C93F]" />
              <span className="ml-3 text-[11px] font-mono text-[#4A4740]">
                devforge — generate_tests
              </span>
            </div>

            {/* Terminal body */}
            <div className="p-5 font-mono text-[11px] leading-[1.7] select-none">

              {/* Command */}
              <div>
                <span className="text-[#D97757]">$</span>
                <span className="text-[#6B6860]"> curl localhost:8001</span>
                <span className="text-[#C8C3B8]">/mcp/</span>
                <span className="text-[#6B6860]"> -H </span>
                <span className="text-[#98C379]">&quot;x-api-key: df_••••••••&quot;</span>
              </div>
              <div className="text-[#4A4740] pl-5">
                -d &apos;&#123;&quot;method&quot;:&quot;tools/call&quot;, &quot;name&quot;:&quot;generate_tests&quot;, ...&#125;&apos;
              </div>

              {/* Spacer */}
              <div className="h-3" />

              {/* Response */}
              <div className="text-[#5A5750]">{"// response"}</div>
              <div className="text-[#C8C3B8]">&#123;</div>
              <div className="pl-5">
                <span className="text-[#9DB4C0]">&quot;filename&quot;</span>
                <span className="text-[#6B6860]">:  </span>
                <span className="text-[#98C379]">&quot;test_calc.py&quot;</span>
                <span className="text-[#6B6860]">,</span>
              </div>
              <div className="pl-5">
                <span className="text-[#9DB4C0]">&quot;validated&quot;</span>
                <span className="text-[#6B6860]">: </span>
                <span className="text-[#D97757] font-semibold">&quot;static&quot;</span>
                <span className="text-[#3D3930]">{" // parse ✓  imports ✓"}</span>
                <span className="text-[#6B6860]">,</span>
              </div>
              <div className="pl-5">
                <span className="text-[#9DB4C0]">&quot;cases&quot;</span>
                <span className="text-[#6B6860]">: [</span>
              </div>
              {[
                "test_add_returns_sum",
                "test_divide_by_zero_raises",
                "test_divide_negative_numbers",
              ].map(c => (
                <div key={c} className="pl-10">
                  <span className="text-[#98C379]">&quot;{c}&quot;</span>
                  <span className="text-[#6B6860]">,</span>
                </div>
              ))}
              <div className="pl-5 text-[#6B6860]">],</div>
              <div className="pl-5">
                <span className="text-[#9DB4C0]">&quot;tokens_used&quot;</span>
                <span className="text-[#6B6860]">: </span>
                <span className="text-[#E5C07B]">312</span>
              </div>
              <div className="text-[#C8C3B8]">&#125;</div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════ TOOLS ════════════════════════════════ */}
      <section id="tools" className="py-24 border-t border-[rgb(var(--border))]">
        <div className="max-w-6xl mx-auto px-6">

          {/* Section heading */}
          <div className="mb-14">
            <p className="text-[10px] font-bold tracking-[0.15em] uppercase text-[rgb(var(--accent))] mb-3">
              Tools
            </p>
            <h2 className="text-3xl font-bold tracking-tight mb-3">Five tools. One API.</h2>
            <p className="text-[rgb(var(--text-muted))] max-w-lg leading-relaxed">
              Each tool is available on the MCP server and REST gateway.
              Pick the integration that fits your workflow.
            </p>
          </div>

          {/* Cards grid — 2+2+1(full) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {tools.map((tool, i) => {
              const Icon = tool.icon;
              const isFeatured = i === 4;

              return (
                <div
                  key={tool.name}
                  className={[
                    "group bg-[rgb(var(--surface))] border border-[rgb(var(--border))] rounded-xl p-6",
                    "hover:border-[rgb(var(--accent)/0.3)] hover:shadow-md transition-all duration-200",
                    isFeatured ? "sm:col-span-2" : "",
                  ].join(" ")}
                >
                  <div className={["flex gap-5", isFeatured ? "sm:items-center" : "flex-col"].join(" ")}>
                    {/* Icon + version */}
                    <div className={["flex items-start justify-between shrink-0", isFeatured ? "sm:flex-col sm:justify-start sm:gap-3" : "mb-1"].join(" ")}>
                      <div className="rounded-lg bg-[rgb(var(--accent-subtle))] p-2.5">
                        <Icon className="h-5 w-5 text-[rgb(var(--accent))]" />
                      </div>
                      <span className="text-[10px] font-mono text-[rgb(var(--text-muted))] bg-[rgb(var(--surface-2))] border border-[rgb(var(--border))] px-2 py-0.5 rounded-full">
                        {tool.version}
                      </span>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-semibold mb-2">{tool.name}</h3>
                      <p className="text-sm text-[rgb(var(--text-muted))] leading-relaxed">
                        {tool.description}
                      </p>

                      <div className="flex flex-wrap items-center gap-3 mt-4">
                        {tool.slug && (
                          <Link
                            href={`/dashboard/playground?tool=${tool.slug}`}
                            className="inline-flex items-center gap-1 text-xs font-medium text-[rgb(var(--accent))] hover:opacity-75 transition-opacity"
                          >
                            Try in playground
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        )}
                        {tool.tags && (
                          <div className="flex flex-wrap gap-1.5">
                            {tool.tags.map(tag => (
                              <span
                                key={tag}
                                className="text-[10px] font-mono px-2 py-0.5 rounded bg-[rgb(var(--surface-2))] border border-[rgb(var(--border))] text-[rgb(var(--text-muted))]"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════ INTEGRATION ══════════════════════════════ */}
      <section id="integration" className="py-24 bg-[#1A1815]">
        <div className="max-w-6xl mx-auto px-6">

          {/* Section heading */}
          <div className="text-center mb-14">
            <p className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#D97757] mb-3">
              Integration
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-[#E8E5DC] mb-4">
              Works with your existing setup.
            </h2>
            <p className="text-[#9E9A8E] max-w-lg mx-auto leading-relaxed mb-8">
              Point Cursor, Claude Desktop, or any MCP-compatible IDE at DevForge.
              Or call the REST gateway from any HTTP client.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {["Cursor", "Claude Desktop", "VS Code MCP", "Windsurf", "Any REST client"].map(c => (
                <DarkPill key={c}>{c}</DarkPill>
              ))}
            </div>
          </div>

          {/* Code blocks */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

            {/* MCP */}
            <div className="rounded-xl border border-[#2E2B26] overflow-hidden bg-[#21201B]">
              <div className="flex items-center gap-3 px-4 py-3 border-b border-[#2E2B26]">
                <span className="text-xs font-semibold text-[#9E9A8E]">MCP · JSON-RPC 2.0</span>
                <span className="ml-auto text-[10px] font-semibold text-[#D97757] bg-[#2E1A12] px-2.5 py-0.5 rounded-full">
                  recommended
                </span>
              </div>
              <pre className="p-5 text-xs font-mono text-[#C8C3B8] overflow-x-auto leading-relaxed">{`{
  "jsonrpc": "2.0",
  "method":  "tools/call",
  "params": {
    "name": "refine_prompt",
    "arguments": {
      "prompt": "add authentication",
      "domain": "code"
    }
  }
}`}</pre>
            </div>

            {/* REST */}
            <div className="rounded-xl border border-[#2E2B26] overflow-hidden bg-[#21201B]">
              <div className="flex items-center px-4 py-3 border-b border-[#2E2B26]">
                <span className="text-xs font-semibold text-[#9E9A8E]">REST · /api/gateway</span>
              </div>
              <pre className="p-5 text-xs font-mono text-[#C8C3B8] overflow-x-auto leading-relaxed">{`curl -X POST http://localhost:8001/api/gateway \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: df_your_key" \\
  -d '{
    "name": "generate_tests",
    "arguments": {
      "code": "def add(a, b): ...",
      "language": "python",
      "module_path": "src.calc"
    }
  }'`}</pre>
            </div>
          </div>

          {/* MCP config */}
          <div className="rounded-xl border border-[#2E2B26] overflow-hidden bg-[#21201B]">
            <div className="flex items-center px-4 py-3 border-b border-[#2E2B26]">
              <span className="text-xs font-semibold text-[#9E9A8E]">
                mcp.json — Cursor / Claude Desktop / Windsurf
              </span>
            </div>
            <pre className="p-5 text-xs font-mono text-[#C8C3B8] overflow-x-auto leading-relaxed">{`{
  "mcpServers": {
    "devforge": {
      "url": "http://localhost:8001/mcp/",
      "headers": { "x-api-key": "df_your_key_here" }
    }
  }
}`}</pre>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════ CTA ═════════════════════════════════ */}
      <section className="py-28 bg-[rgb(var(--accent))]">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-bold text-white tracking-tight mb-5">
            Start building in 60 seconds.
          </h2>
          <p className="text-lg text-white/75 leading-relaxed mb-12 max-w-xl mx-auto">
            Get your API key, point your MCP client at DevForge, and your first tool
            call is live. No configuration, no setup, no YAML.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-4">
            <Link
              href="/register"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl text-sm font-semibold bg-white text-[rgb(var(--accent))] hover:bg-white/90 transition-colors"
              style={{ boxShadow: "0 2px 20px rgba(0,0,0,0.15)" }}
            >
              Get started free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard/docs"
              className="inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl text-sm font-semibold border-2 border-white/35 text-white hover:bg-white/10 hover:border-white/55 transition-colors"
            >
              Explore docs
            </Link>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════ FOOTER ═══════════════════════════════ */}
      <footer className="border-t border-[rgb(var(--border))] py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-5">
          <Logo size="sm" />
          <div className="flex items-center gap-6 text-sm text-[rgb(var(--text-muted))]">
            <Link href="/dashboard/docs"       className="hover:text-[rgb(var(--text))] transition-colors">Docs</Link>
            <Link href="/dashboard/playground" className="hover:text-[rgb(var(--text))] transition-colors">Playground</Link>
            <Link href="/login"                className="hover:text-[rgb(var(--text))] transition-colors">Sign in</Link>
            <Link href="/register"             className="hover:text-[rgb(var(--text))] transition-colors">Register</Link>
          </div>
          <p className="text-xs text-[rgb(var(--text-muted))]">© 2026 DevForge</p>
        </div>
      </footer>

    </div>
  );
}
