import Link from "next/link";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { ArrowLeft, Check } from "lucide-react";

const features = [
  "AI test generation with tree-sitter static validation",
  "Evidence-based prompt refining — no hallucinated APIs",
  "26-op GitHub automation, natural language or structured",
  "Realistic mock data with configurable realism levels",
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex">

      {/* ── Left panel — always dark, branded ── */}
      <div className="hidden lg:flex flex-col w-[420px] shrink-0 relative overflow-hidden bg-[#1A1815]">
        {/* Dot grid */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
        {/* Coral glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(ellipse 80% 50% at 0% 0%, rgba(217,119,87,0.14), transparent)",
          }}
        />

        <div className="relative z-10 flex flex-col h-full p-10">
          {/* Logo — inline so it's always light on the dark panel */}
          <Link href="/" className="flex items-center gap-2 select-none">
            <div className="flex items-center justify-center h-8 w-8 rounded-md bg-[#D97757] shrink-0">
              <span className="font-bold text-white text-sm leading-none">D</span>
            </div>
            <span className="font-semibold text-[#E8E5DC] text-base">DevForge</span>
          </Link>

          {/* Main copy */}
          <div className="flex-1 flex flex-col justify-center">
            <p className="text-[10px] font-bold tracking-[0.15em] uppercase text-[#D97757] mb-4">
              AI Developer Platform
            </p>
            <h2 className="text-3xl font-bold text-[#E8E5DC] tracking-tight leading-[1.15] mb-4">
              Developer tools<br />
              that <span className="text-[#D97757]">know</span><br />
              your stack.
            </h2>
            <p className="text-[#6B6860] text-sm mb-8 leading-relaxed">
              Five AI tools. One MCP server.<br />
              Connect from Cursor, Claude Desktop, or any REST client.
            </p>

            <div className="space-y-3.5">
              {features.map((f) => (
                <div key={f} className="flex items-start gap-3">
                  <div className="mt-0.5 h-4 w-4 rounded-full bg-[#D97757]/15 flex items-center justify-center shrink-0">
                    <Check className="h-2.5 w-2.5 text-[#D97757]" />
                  </div>
                  <span className="text-[#9E9A8E] text-sm leading-snug">{f}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Mini terminal */}
          <div className="rounded-xl border border-[#2E2B26] overflow-hidden bg-[#141210] mb-6">
            <div className="flex items-center gap-1.5 px-3 py-2.5 border-b border-[#2E2B26]">
              <div className="h-2.5 w-2.5 rounded-full bg-[#FF5F56]" />
              <div className="h-2.5 w-2.5 rounded-full bg-[#FFBD2E]" />
              <div className="h-2.5 w-2.5 rounded-full bg-[#27C93F]" />
              <span className="ml-1.5 text-[10px] font-mono text-[#4A4740]">devforge — generate_tests</span>
            </div>
            <div className="p-3.5 font-mono text-[11px] leading-[1.75] select-none">
              <div>
                <span className="text-[#D97757]">$</span>
                <span className="text-[#6B6860]"> curl localhost:8001/mcp/ -H </span>
                <span className="text-[#98C379]">&quot;x-api-key: df_••••&quot;</span>
              </div>
              <div className="h-2" />
              <div className="text-[#C8C3B8]">&#123;</div>
              <div className="pl-4">
                <span className="text-[#9DB4C0]">&quot;validated&quot;</span>
                <span className="text-[#6B6860]">: </span>
                <span className="text-[#D97757] font-semibold">&quot;static&quot;</span>
                <span className="text-[#3D3930]">{" // parse ✓  imports ✓"}</span>
              </div>
              <div className="pl-4">
                <span className="text-[#9DB4C0]">&quot;cases&quot;</span>
                <span className="text-[#6B6860]">: [</span>
                <span className="text-[#98C379]">&quot;test_add&quot;</span>
                <span className="text-[#6B6860]">, </span>
                <span className="text-[#98C379]">&quot;test_divide&quot;</span>
                <span className="text-[#6B6860]">]</span>
              </div>
              <div className="text-[#C8C3B8]">&#125;</div>
            </div>
          </div>

          <p className="text-[#3D3930] text-xs">© 2026 DevForge</p>
        </div>
      </div>

      {/* ── Right panel — form area ── */}
      <div
        className="flex-1 flex flex-col bg-[rgb(var(--bg))] relative"
        style={{
          backgroundImage: "radial-gradient(circle, rgb(var(--border)) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
        }}
      >
        {/* Radial glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(ellipse 80% 40% at 50% -10%, rgb(var(--accent-subtle)), transparent)",
          }}
        />

        {/* Top bar */}
        <div className="relative z-10 flex items-center justify-between px-6 h-14">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm font-medium text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text))] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Home
          </Link>
          <ThemeToggle />
        </div>

        {/* Mobile logo — hidden on desktop where left panel shows it */}
        <div className="relative z-10 flex justify-center mt-4 lg:hidden">
          <Link href="/">
            <Logo size="md" />
          </Link>
        </div>

        {/* Centered form */}
        <div className="relative z-10 flex flex-1 items-center justify-center px-6 pb-14 pt-6 lg:pt-0">
          {children}
        </div>
      </div>

    </div>
  );
}
