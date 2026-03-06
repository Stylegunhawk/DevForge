import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ keyId: string }> }
) {
  const { keyId } = await params;
  const backendUrl = `http://localhost:8001/api/admin/keys/${keyId}/overrides`;
  const headers = new Headers(request.headers);
  
  // Remove host header to avoid conflicts
  headers.delete('host');

  try {
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers,
    });

    const responseData = await response.text();

    // Add CORS headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      if (key !== 'access-control-allow-origin') {
        responseHeaders.set(key, value);
      }
    });
    responseHeaders.set('Access-Control-Allow-Origin', 'http://localhost:3000');
    responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    responseHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    return new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('GET key overrides proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request to backend' },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ keyId: string }> }
) {
  const { keyId } = await params;
  const backendUrl = `http://localhost:8001/api/admin/keys/${keyId}/overrides`;
  const headers = new Headers(request.headers);
  
  // Remove host header to avoid conflicts
  headers.delete('host');

  try {
    const body = await request.text();
    
    const response = await fetch(backendUrl, {
      method: 'PATCH',
      headers,
      body: body
    });

    const responseData = await response.text();

    // Add CORS headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      if (key !== 'access-control-allow-origin') {
        responseHeaders.set(key, value);
      }
    });
    responseHeaders.set('Access-Control-Allow-Origin', 'http://localhost:3000');
    responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    responseHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    return new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('PATCH key overrides proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request to backend' },
      { status: 500 }
    );
  }
}

export async function OPTIONS() {
  const response = new NextResponse(null, { status: 200 });
  response.headers.set('Access-Control-Allow-Origin', 'http://localhost:3000');
  response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  return response;
}
