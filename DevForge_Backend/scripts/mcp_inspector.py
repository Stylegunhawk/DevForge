#!/usr/bin/env python3
"""MCP Inspector - Interactive CLI for testing DevForge backend tools.

Usage:
    python scripts/mcp_inspector.py -i                    # Interactive mode
    python scripts/mcp_inspector.py --manifest            # View manifest only
    python scripts/mcp_inspector.py --tool generate_data --args '{"rows": 5}'
    python scripts/mcp_inspector.py --tool generate_cheatsheet --language python --skill_level intermediate
"""

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional

import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

# Default backend URL
DEFAULT_BACKEND_URL = "http://localhost:8000"

# Example payloads for all tools
EXAMPLE_PAYLOADS = {
    "generate_data": {
        "name": "generate_data",
        "arguments": {"rows": 10, "format": "json", "fields": ["name", "email"]},
    },
    "retrieve_docs": {
        "name": "retrieve_docs",
        "arguments": {"query": "How to use FastAPI?", "top_k": 5},
    },
    "github_operation": {
        "name": "github_operation",
        "arguments": {"query": "List my repositories"},
    },
    "rerank_docs": {
        "name": "rerank_docs",
        "arguments": {
            "query": "Python async programming",
            "documents": ["Document 1 about Python", "Document 2 about async"],
            "top_k": 2,
        },
    },
    "refine_prompt": {
        "name": "refine_prompt",
        "arguments": {
            "prompt": "Create a REST API",
            "domain": "code",
            "skill_level": "intermediate",
        },
    },
    "generate_cheatsheet": {
        "name": "generate_cheatsheet",
        "arguments": {"language": "python", "skill_level": "intermediate"},
    },
}

console = Console()


def fetch_manifest(backend_url: str) -> Optional[Dict[str, Any]]:
    """Fetch manifest from backend."""
    try:
        response = httpx.get(f"{backend_url}/api/manifests/devforge.json", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        console.print(f"[red]❌ Failed to fetch manifest: {e}[/red]")
        return None


def call_tool(backend_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool via the gateway endpoint."""
    payload = {
        "apiName": tool_name,
        "arguments": arguments,
    }

    start_time = time.time()

    try:
        response = httpx.post(
            f"{backend_url}/api/gateway",
            json=payload,
            timeout=60.0,  # Tools might take time
        )
        response.raise_for_status()
        result = response.json()
        execution_time = time.time() - start_time

        return {
            "success": True,
            "status_code": response.status_code,
            "result": result,
            "execution_time": execution_time,
        }
    except httpx.HTTPStatusError as e:
        execution_time = time.time() - start_time
        try:
            error_body = e.response.json()
        except:
            error_body = e.response.text

        return {
            "success": False,
            "status_code": e.response.status_code,
            "result": error_body,
            "execution_time": execution_time,
            "error": str(e),
        }
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            "success": False,
            "status_code": None,
            "result": None,
            "execution_time": execution_time,
            "error": str(e),
        }


def display_manifest(manifest: Dict[str, Any]):
    """Display manifest in a formatted table."""
    console.print("\n[bold cyan]📋 DevForge Manifest[/bold cyan]\n")

    # Basic info
    info_table = Table(show_header=False, box=None)
    info_table.add_row("[bold]Name:[/bold]", manifest.get("name", "N/A"))
    info_table.add_row("[bold]Version:[/bold]", manifest.get("meta", {}).get("version", "N/A"))
    info_table.add_row(
        "[bold]Description:[/bold]", manifest.get("meta", {}).get("description", "N/A")
    )
    info_table.add_row("[bold]Gateway:[/bold]", manifest.get("gateway", "N/A"))
    console.print(info_table)

    # Tools list
    tools = manifest.get("api", [])
    if tools:
        console.print(f"\n[bold]Available Tools:[/bold] {len(tools)}\n")
        tools_table = Table(show_header=True, header_style="bold magenta")
        tools_table.add_column("Tool Name", style="cyan")
        tools_table.add_column("Description", style="white")

        for tool in tools:
            name = tool.get("name", "N/A")
            desc = tool.get("description", "No description")
            # Truncate long descriptions
            if len(desc) > 60:
                desc = desc[:57] + "..."
            tools_table.add_row(name, desc)

        console.print(tools_table)
    else:
        console.print("[yellow]⚠️  No tools found in manifest[/yellow]")


def display_request_response(tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]):
    """Display formatted request and response."""
    console.print(f"\n[bold cyan]🔧 Testing Tool: {tool_name}[/bold cyan]\n")

    # Request
    request_payload = {
        "apiName": tool_name,
        "arguments": arguments,
    }
    console.print("[bold]📤 Request:[/bold]")
    console.print(JSON(json.dumps(request_payload)))

    # Response
    console.print(f"\n[bold]📊 Status Code:[/bold] {result.get('status_code', 'N/A')}")

    if result.get("success"):
        console.print("\n[bold]📥 Response:[/bold]")
        console.print(JSON(json.dumps(result["result"], indent=2)))

        # Check response format
        response_data = result["result"]
        if isinstance(response_data, dict):
            if "success" in response_data and "data" in response_data:
                console.print("\n[green]✅ Response format is correct![/green]")
            else:
                console.print(
                    "\n[yellow]⚠️  Response format might be incorrect (missing 'success' or 'data')[/yellow]"
                )
    else:
        console.print("\n[bold red]❌ Error:[/bold red]")
        if result.get("error"):
            console.print(f"[red]{result['error']}[/red]")
        if result.get("result"):
            console.print(JSON(json.dumps(result["result"], indent=2)))

    # Execution time
    exec_time = result.get("execution_time", 0)
    console.print(f"\n[dim]⏱️  Execution time: {exec_time:.3f}s[/dim]")


def interactive_mode(backend_url: str):
    """Run in interactive mode."""
    console.print("[bold cyan]🔍 MCP Inspector - Interactive Mode[/bold cyan]\n")

    # Fetch manifest
    manifest = fetch_manifest(backend_url)
    if not manifest:
        console.print("[red]❌ Cannot connect to backend. Make sure it's running on {backend_url}[/red]")
        return

    display_manifest(manifest)

    tools = manifest.get("api", [])
    tool_names = [tool.get("name") for tool in tools if tool.get("name")]

    while True:
        console.print("\n[bold]Options:[/bold]")
        console.print("1. Test a tool")
        console.print("2. View manifest again")
        console.print("3. Exit")

        choice = input("\nEnter choice (1-3): ").strip()

        if choice == "1":
            console.print("\n[bold]Available tools:[/bold]")
            for i, tool_name in enumerate(tool_names, 1):
                console.print(f"  {i}. {tool_name}")

            try:
                tool_choice = int(input("\nSelect tool number: ").strip())
                if 1 <= tool_choice <= len(tool_names):
                    tool_name = tool_names[tool_choice - 1]

                    # Get example payload
                    example = EXAMPLE_PAYLOADS.get(tool_name, {})
                    console.print(f"\n[bold]Example arguments for {tool_name}:[/bold]")
                    console.print(JSON(json.dumps(example.get("arguments", {}), indent=2)))

                    args_input = input("\nEnter arguments (JSON) or press Enter for example: ").strip()
                    if args_input:
                        try:
                            arguments = json.loads(args_input)
                        except json.JSONDecodeError:
                            console.print("[red]❌ Invalid JSON. Using example arguments.[/red]")
                            arguments = example.get("arguments", {})
                    else:
                        arguments = example.get("arguments", {})

                    # Call tool
                    result = call_tool(backend_url, tool_name, arguments)
                    display_request_response(tool_name, arguments, result)

                else:
                    console.print("[red]❌ Invalid tool number[/red]")
            except (ValueError, KeyboardInterrupt):
                console.print("\n[yellow]Cancelled[/yellow]")

        elif choice == "2":
            display_manifest(manifest)

        elif choice == "3":
            console.print("\n[green]👋 Goodbye![/green]")
            break

        else:
            console.print("[red]❌ Invalid choice[/red]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Inspector - Test DevForge backend tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument("--manifest", action="store_true", help="Display manifest only")
    parser.add_argument("--tool", type=str, help="Tool name to test")
    parser.add_argument("--args", type=str, help="JSON arguments for tool")
    parser.add_argument("--backend-url", type=str, default=DEFAULT_BACKEND_URL, help="Backend URL")
    parser.add_argument("--language", type=str, help="Language for generate_cheatsheet")
    parser.add_argument("--skill_level", type=str, help="Skill level for generate_cheatsheet")
    parser.add_argument("--code_context", type=str, help="Code context for generate_cheatsheet")

    args = parser.parse_args()

    # Interactive mode
    if args.interactive:
        interactive_mode(args.backend_url)
        return

    # Manifest only
    if args.manifest:
        manifest = fetch_manifest(args.backend_url)
        if manifest:
            display_manifest(manifest)
        return

    # Tool testing
    if args.tool:
        # Build arguments
        if args.args:
            try:
                arguments = json.loads(args.args)
            except json.JSONDecodeError as e:
                console.print(f"[red]❌ Invalid JSON in --args: {e}[/red]")
                sys.exit(1)
        elif args.tool == "generate_cheatsheet":
            # Special handling for cheat sheet
            arguments = {}
            if args.language:
                arguments["language"] = args.language
            if args.skill_level:
                arguments["skill_level"] = args.skill_level
            if args.code_context:
                arguments["code_context"] = args.code_context
            if not arguments:
                # Use example
                arguments = EXAMPLE_PAYLOADS["generate_cheatsheet"]["arguments"]
        else:
            # Use example payload
            example = EXAMPLE_PAYLOADS.get(args.tool, {})
            arguments = example.get("arguments", {})
            if not arguments:
                console.print(f"[yellow]⚠️  No example payload for {args.tool}. Using empty arguments.[/yellow]")
                arguments = {}

        # Call tool
        result = call_tool(args.backend_url, args.tool, arguments)
        display_request_response(args.tool, arguments, result)

        # Exit with error code if failed
        if not result.get("success"):
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

