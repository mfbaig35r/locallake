"use client";

import { Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useCreateSchedule,
  useNotebooks,
} from "@/lib/api/hooks";

export function NewScheduleModal({
  open,
  onClose,
  initialNotebookPath,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  initialNotebookPath?: string;
  onCreated?: (scheduleId: string) => void;
}) {
  const notebooks = useNotebooks();
  const create = useCreateSchedule();
  const [notebookPath, setNotebookPath] = useState<string>("");
  const [cron, setCron] = useState<string>("0 * * * *");
  const [paramsText, setParamsText] = useState<string>("{}");
  const [enabled, setEnabled] = useState<boolean>(true);
  const [maxRetries, setMaxRetries] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setCron("0 * * * *");
    setParamsText("{}");
    setEnabled(true);
    setMaxRetries(0);
    if (initialNotebookPath) {
      setNotebookPath(initialNotebookPath);
    } else {
      const first = notebooks.data?.items?.[0]?.path;
      if (first) setNotebookPath(first);
    }
  }, [open, initialNotebookPath, notebooks.data]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let parameters: Record<string, unknown>;
    try {
      const parsed = JSON.parse(paramsText || "{}");
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("parameters must be a JSON object");
      }
      parameters = parsed as Record<string, unknown>;
    } catch (err) {
      setError(err instanceof Error ? err.message : "invalid JSON");
      return;
    }
    try {
      const result = await create.mutateAsync({
        notebook_path: notebookPath,
        cron_expression: cron,
        parameters,
        enabled,
        max_retries: maxRetries,
      });
      onCreated?.(result.id);
      onClose();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "detail" in err) {
        setError(String((err as { detail: unknown }).detail));
      } else {
        setError(err instanceof Error ? err.message : "create failed");
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-background/60 backdrop-blur-sm"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="document"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">New schedule</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Notebook
            </span>
            {notebooks.isLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
              </div>
            ) : (
              <select
                value={notebookPath}
                onChange={(e) => setNotebookPath(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-2 font-mono text-sm"
              >
                {(notebooks.data?.items ?? []).map((nb) => (
                  <option key={nb.path} value={nb.path}>
                    {nb.path}
                  </option>
                ))}
              </select>
            )}
          </label>

          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Cron expression
            </span>
            <Input
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="0 * * * *"
              className="font-mono text-sm"
            />
            <p className="text-[11px] text-muted-foreground">
              UTC. Try <code>0 * * * *</code> (hourly), <code>*/15 * * * *</code> (every 15m),{" "}
              <code>0 9 * * 1-5</code> (9am weekdays).
            </p>
          </label>

          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Parameters (JSON)
            </span>
            <textarea
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
              rows={3}
              className="block w-full rounded-md border border-input bg-background px-2 py-1.5 font-mono text-xs"
            />
          </label>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            Enabled
          </label>

          <label className="block space-y-1">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Max retries
            </span>
            <Input
              type="number"
              min={0}
              max={10}
              value={maxRetries}
              onChange={(e) => setMaxRetries(Number(e.target.value) || 0)}
              className="w-24 font-mono text-sm"
            />
            <p className="text-[11px] text-muted-foreground">
              On failure, the worker enqueues up to N retries (60s apart). 0 = no retries.
            </p>
          </label>

          {error ? (
            <p className="rounded-md bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onClose}
              disabled={create.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={create.isPending || !notebookPath}>
              {create.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Create
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
