import { NextResponse, type NextRequest } from "next/server";
import {
  COOKIE,
  authEnabled,
  signSessionCookie,
  verifyPassword,
} from "@/lib/auth";

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => null)) as { password?: string } | null;
  if (!authEnabled()) {
    return NextResponse.json({ ok: true, authEnabled: false });
  }
  const password = body?.password ?? "";
  const ok = await verifyPassword(password);
  if (!ok) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }
  const value = await signSessionCookie(process.env.LOCALLAKE_PASSWORD!);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, value, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(COOKIE);
  return res;
}
