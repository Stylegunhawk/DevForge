import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

export async function POST(request: NextRequest) {
  const headers = new Headers();
  headers.set('Content-Type', 'application/json');

  const apiKey = request.headers.get('x-api-key');
  if (apiKey) {
    headers.set('x-api-key', apiKey);
  }

  try {
    const body = await request.text();
    const response = await fetch(`${BACKEND_URL}/api/gateway`, {
      method: 'POST',
      headers,
      body,
    });

    const data = await response.text();
    return new NextResponse(data, {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('Gateway proxy error:', error);
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 });
  }
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, x-api-key',
    },
  });
}
