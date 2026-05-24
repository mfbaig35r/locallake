import { NextResponse, type NextRequest } from "next/server";
import { COOKIE, authEnabled, verifySessionCookie } from "@/lib/auth";

export const config = {
  matcher: ["/((?!login|api/auth|_next|favicon.ico).*)"],
};

export async function proxy(req: NextRequest) {
  if (!authEnabled()) return NextResponse.next();

  const value = req.cookies.get(COOKIE)?.value ?? "";
  const ok = await verifySessionCookie(value);
  if (ok) return NextResponse.next();

  const login = new URL("/login", req.url);
  login.searchParams.set("from", req.nextUrl.pathname);
  return NextResponse.redirect(login);
}
