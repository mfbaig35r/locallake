"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

const FOOTER_SENTINEL = "=== run complete ===";
// Strip ANSI escape sequences (CSI/OSC) before rendering.
const ANSI_RE = /\[[0-9;?]*[ -/]*[@-~]|\][^]*/g;

type State = "connecting" | "open" | "closed" | "error";

export function LogStream({ jobId }: { jobId: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [state, setState] = useState<State>("connecting");
  const [follow, setFollow] = useState(true);
  const buffer = useRef<string>("");
  const followRef = useRef(follow);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  followRef.current = follow;

  useEffect(() => {
    const url = wsUrl(`/jobs/${encodeURIComponent(jobId)}/logs`);
    const ws = new WebSocket(url);
    setState("connecting");

    ws.onopen = () => setState("open");
    ws.onerror = () => setState("error");
    ws.onclose = () => setState("closed");
    ws.onmessage = (ev) => {
      const text = typeof ev.data === "string" ? ev.data : "";
      buffer.current += text.replace(ANSI_RE, "");
      const parts = buffer.current.split("\n");
      buffer.current = parts.pop() ?? "";
      if (parts.length === 0) return;
      setLines((prev) => prev.concat(parts));
    };

    return () => {
      try {
        ws.close();
      } catch {
        // socket already closed by the server.
      }
    };
  }, [jobId]);

  useEffect(() => {
    if (!followRef.current) return;
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines]);

  const footerSeen = lines.some((line) => line.includes(FOOTER_SENTINEL));

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={[
              "h-1.5 w-1.5 rounded-full",
              state === "open"
                ? "bg-emerald-500"
                : state === "connecting"
                  ? "bg-amber-500 animate-pulse"
                  : state === "error"
                    ? "bg-destructive"
                    : "bg-muted-foreground/40",
            ].join(" ")}
          />
          <span className="font-mono">
            {state === "open"
              ? footerSeen
                ? "stream complete"
                : "streaming"
              : state}
          </span>
          <span className="text-muted-foreground/60">·</span>
          <span>{lines.length} lines</span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setFollow((v) => !v)}
          title={follow ? "Pause autoscroll" : "Resume autoscroll"}
        >
          {follow ? (
            <>
              <Pause className="h-3.5 w-3.5" /> Pause
            </>
          ) : (
            <>
              <Play className="h-3.5 w-3.5" /> Follow
            </>
          )}
        </Button>
      </div>

      <div
        ref={scrollerRef}
        className="max-h-[420px] min-h-[200px] overflow-auto bg-muted/40 px-3 py-2 font-mono text-xs leading-relaxed"
      >
        {lines.length === 0 ? (
          <div className="text-muted-foreground">
            Waiting for output…
            <br />
            Use{" "}
            <code className="rounded bg-muted/40 px-1">__lake__.log("…")</code>{" "}
            for live progress; <code className="rounded bg-muted/40 px-1">print()</code>{" "}
            appears when the run finishes.
          </div>
        ) : (
          lines.map((line, i) => (
            <pre key={i} className="whitespace-pre-wrap break-all">
              {line || " "}
            </pre>
          ))
        )}
      </div>
    </div>
  );
}

function wsUrl(path: string): string {
  if (typeof window === "undefined") return "";
  const explicit = process.env.NEXT_PUBLIC_API_URL;
  const base = explicit ?? window.location.origin.replace(":3000", ":8000");
  const u = new URL(base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  u.pathname = path;
  return u.toString();
}
