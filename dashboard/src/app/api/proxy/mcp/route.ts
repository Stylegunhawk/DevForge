import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

// Trailing slash is mandatory — FastMCP mounts at /mcp, not /mcp/
const MCP_URL = `${BACKEND_URL}/mcp/`;

// Headers the MCP Streamable HTTP transport requires
const MCP_ACCEPT = 'application/json, text/event-stream';

export async function POST(request: NextRequest) {
  const reqHeaders = new Headers();
  reqHeaders.set('Content-Type', 'application/json');
  reqHeaders.set('Accept', MCP_ACCEPT);

  const apiKey = request.headers.get('x-api-key');
  if (apiKey) reqHeaders.set('x-api-key', apiKey);

  try {
    const body = await request.text();
    const upstream = await fetch(MCP_URL, {
      method: 'POST',
      headers: reqHeaders,
      body,
    });

    const data = await upstream.text();

    // Forward rate-limit headers so the playground can display them
    const resHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
    for (const name of upstream.headers.keys()) {
      if (name.toLowerCase().startsWith('x-ratelimit')) {
        resHeaders[name] = upstream.headers.get(name)!;
      }
    }

    return new NextResponse(data, { status: upstream.status, headers: resHeaders });
  } catch (error) {
    console.error('MCP proxy error:', error);
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 });
  }
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, x-api-key, Accept',
    },
  });
}
