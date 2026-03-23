import { NextRequest, NextResponse } from "next/server";

const SITE_PASSWORD = process.env.SITE_PASSWORD || "ProtoExtract1!";
const AUTH_COOKIE = "proto_auth";

export function middleware(request: NextRequest) {
  // Skip auth for API routes and static files
  if (
    request.nextUrl.pathname.startsWith("/api") ||
    request.nextUrl.pathname.startsWith("/_next") ||
    request.nextUrl.pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // Check for auth cookie
  const authCookie = request.cookies.get(AUTH_COOKIE);
  if (authCookie?.value === "authenticated") {
    return NextResponse.next();
  }

  // Check for login form submission
  if (request.nextUrl.pathname === "/login" && request.method === "POST") {
    return NextResponse.next();
  }

  // Check for password in URL params (for simple login)
  const password = request.nextUrl.searchParams.get("password");
  if (password === SITE_PASSWORD) {
    const response = NextResponse.redirect(new URL("/", request.url));
    response.cookies.set(AUTH_COOKIE, "authenticated", {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });
    return response;
  }

  // Show login page
  if (request.nextUrl.pathname !== "/login") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
