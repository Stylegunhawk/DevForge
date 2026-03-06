import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import CopyButton from "@/components/copy-button";
import { Wand2, Database, FileCode, Github } from "lucide-react";

const curlExample = `curl -X POST https://api.devforge.ai/api/gateway \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -d '{"name": "refine_prompt", \\
       "arguments": {"prompt": "Your prompt here"}}'`;

const authHeader = `x-api-key: df_your_key_here`;

const mcpConfig = `{
  "mcpServers": {
    "devforge": {
      "url": "http://localhost:8001/mcp",
      "headers": {
        "x-api-key": "YOUR_API_KEY"
      }
    }
  }
}`;

const successResponse = `{"success": true, "data": {...}, "message": "tool executed successfully"}`;

const errorResponse = `{"success": false, "detail": "Error message"}`;

const tools = [
  {
    icon: Wand2,
    title: "Prompt Refiner",
    description: "Enhance and optimize prompts for better AI outputs",
    arguments: [
      { name: "prompt", type: "string", required: true },
      { name: "domain", type: "string", required: false }
    ]
  },
  {
    icon: Database,
    title: "Data Generator",
    description: "Generate realistic mock data in JSON or CSV format",
    arguments: [
      { name: "rows", type: "number", required: true },
      { name: "format", type: "json|csv", required: true },
      { name: "fields", type: "array of strings", required: true }
    ]
  },
  {
    icon: FileCode,
    title: "Cheatsheet Generator",
    description: "Generate code cheatsheets for any programming language",
    arguments: [
      { name: "language", type: "string", required: true },
      { name: "skill_level", type: "beginner|intermediate|advanced", required: true },
      { name: "code_context", type: "string", required: false }
    ]
  },
  {
    icon: Github,
    title: "GitHub Operations",
    description: "Perform GitHub operations like listing repos and generating commit messages",
    arguments: [
      { name: "query", type: "string", required: true },
      { name: "context.github_token", type: "string", required: true }
    ]
  }
];

export default function DocsPage() {
  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Documentation</h1>
        <p className="text-zinc-500">Learn how to integrate with DevForge API</p>
      </div>

      {/* Quick Start */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">Quick Start</h2>
        <Card>
          <CardContent className="p-6">
            <p className="mb-4">Start making API calls with this simple curl example:</p>
            <div className="relative">
              <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 font-mono text-sm rounded-lg p-4 overflow-x-auto">
                <code>{curlExample}</code>
              </pre>
              <CopyButton text={curlExample} />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Authentication */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">Authentication</h2>
        <Card>
          <CardContent className="p-6">
            <p className="mb-4">
              All requests require an <code className="bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded text-sm">x-api-key</code> header.
              Get your API key from the API Keys page.
            </p>
            <div className="relative">
              <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 font-mono text-sm rounded-lg p-4">
                <code>{authHeader}</code>
              </pre>
              <CopyButton text={authHeader} />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Available Tools */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">Available Tools</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {tools.map((tool, index) => {
            const Icon = tool.icon;
            return (
              <Card key={index} className="border rounded-lg p-4 hover:border-indigo-500 transition-colors">
                <CardHeader className="pb-4">
                  <div className="flex items-center space-x-3">
                    <Icon className="h-6 w-6 text-indigo-600" />
                    <CardTitle className="text-lg">{tool.title}</CardTitle>
                  </div>
                  <CardDescription>{tool.description}</CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Arguments:</p>
                    <div className="flex flex-wrap gap-2">
                      {tool.arguments.map((arg, argIndex) => (
                        <Badge key={argIndex} variant="outline" className="text-xs">
                          {arg.name}
                          <span className="ml-1 text-zinc-500">({arg.type})</span>
                          {arg.required && <span className="ml-1 text-red-500">*</span>}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* MCP Integration */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">MCP Integration (Cursor IDE)</h2>
        <Card>
          <CardContent className="p-6">
            <p className="mb-4">
              Connect DevForge directly to Cursor IDE using the Model Context Protocol.
              Add this configuration to your Cursor MCP settings:
            </p>
            <div className="relative">
              <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 font-mono text-sm rounded-lg p-4 overflow-x-auto">
                <code>{mcpConfig}</code>
              </pre>
              <CopyButton text={mcpConfig} />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Response Format */}
      <section>
        <h2 className="text-2xl font-semibold mb-4">Response Format</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg text-green-600">Success Response</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 font-mono text-sm rounded-lg p-4">
                  <code>{successResponse}</code>
                </pre>
                <CopyButton text={successResponse} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg text-red-600">Error Response</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <pre className="bg-zinc-950 dark:bg-zinc-900 text-zinc-100 font-mono text-sm rounded-lg p-4">
                  <code>{errorResponse}</code>
                </pre>
                <CopyButton text={errorResponse} />
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
