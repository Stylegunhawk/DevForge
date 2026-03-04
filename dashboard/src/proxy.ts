import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Protect dashboard routes
  if (pathname.startsWith("/dashboard")) {
    const token = await getToken({ 
      req: request, 
      secret: process.env.NEXTAUTH_SECRET 
    });

    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }

  // Protect admin routes
  if (pathname.startsWith("/dashboard/admin")) {
    const token = await getToken({ 
      req: request, 
      secret: process.env.NEXTAUTH_SECRET 
    });

    if (!token || !token.isAdmin) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  // Redirect authenticated users away from auth pages
  if (pathname === "/login" || pathname === "/register") {
    const token = await getToken({ 
      req: request, 
      secret: process.env.NEXTAUTH_SECRET 
    });

    if (token) {
      return NextResponse.redirect(new URL("/dashboard/keys", request.url));
    }
  }

  return NextResponse.next();
}
