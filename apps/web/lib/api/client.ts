import createClient from "openapi-fetch";
import type { paths } from "./types";

const baseUrl =
  (typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_URL
    : window.location.origin.replace(":3000", ":8000")) ?? "http://localhost:8000";

export const api = createClient<paths>({
  baseUrl,
  credentials: "include",
});
