/**
 * Single-user auth. When LOCALLAKE_PASSWORD is unset, auth is disabled and
 * the middleware lets everything through. When set, the cookie holds an
 * HMAC of a fixed marker so it's tamper-resistant — and stops working
 * (cleanly invalidates all sessions) if the password rotates.
 *
 * The HMAC scheme is intentionally tiny: SHA-256 over the password yields
 * a 32-byte secret; we sign the literal string "v1" and store base64url
 * of the digest. Validation re-derives + compares in constant time.
 */

const COOKIE_NAME = "locallake-auth";
const MARKER = "v1";

const enc = new TextEncoder();

async function importKey(password: string): Promise<CryptoKey> {
  const secret = await crypto.subtle.digest("SHA-256", enc.encode(password));
  return crypto.subtle.importKey(
    "raw",
    secret,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

function toBase64Url(bytes: ArrayBuffer): string {
  const b = Buffer.from(bytes);
  return b
    .toString("base64")
    .replace(/=+$/, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function fromBase64Url(s: string): ArrayBuffer {
  const padded = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const buf = Buffer.from(padded, "base64");
  // Copy into a standalone ArrayBuffer so the type doesn't widen to SharedArrayBuffer
  const out = new ArrayBuffer(buf.length);
  new Uint8Array(out).set(buf);
  return out;
}

export const COOKIE = COOKIE_NAME;

export function authEnabled(): boolean {
  return !!process.env.LOCALLAKE_PASSWORD;
}

export async function signSessionCookie(password: string): Promise<string> {
  const key = await importKey(password);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(MARKER));
  return toBase64Url(sig);
}

export async function verifySessionCookie(value: string): Promise<boolean> {
  const password = process.env.LOCALLAKE_PASSWORD;
  if (!password) return true;
  if (!value) return false;
  try {
    const key = await importKey(password);
    return await crypto.subtle.verify(
      "HMAC",
      key,
      fromBase64Url(value),
      enc.encode(MARKER)
    );
  } catch {
    return false;
  }
}

export async function verifyPassword(input: string): Promise<boolean> {
  const password = process.env.LOCALLAKE_PASSWORD;
  if (!password) return true;
  // constant-time-ish compare via HMAC equality
  const sig1 = await signSessionCookie(password);
  const sig2 = await signSessionCookie(input);
  if (sig1.length !== sig2.length) return false;
  let diff = 0;
  for (let i = 0; i < sig1.length; i++) {
    diff |= sig1.charCodeAt(i) ^ sig2.charCodeAt(i);
  }
  return diff === 0;
}
