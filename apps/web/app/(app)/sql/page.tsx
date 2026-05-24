"use client";

import { Bookmark, History, Loader2, Play, Save, Trash2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ResultsGrid } from "@/components/sql/results-grid";
import { SqlEditor } from "@/components/sql/sql-editor";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  useCreateSavedQuery,
  useDeleteSavedQuery,
  useQueryHistory,
  useRunQuery,
  useSavedQueries,
} from "@/lib/api/hooks";
import { formatDuration, formatRelativeTime } from "@/lib/utils";

const DEFAULT_SQL = "-- Cmd/Ctrl + Enter to run\nSELECT 1 AS hello;";

type PanelKind = "saved" | "history" | null;

export default function SqlPage() {
  const [sql, setSql] = useState<string>(DEFAULT_SQL);
  const [panel, setPanel] = useState<PanelKind>(null);
  const [saveName, setSaveName] = useState<string>("");
  const runQuery = useRunQuery();
  const saved = useSavedQueries();
  const createSaved = useCreateSavedQuery();
  const deleteSaved = useDeleteSavedQuery();
  const history = useQueryHistory(50);

  const result = runQuery.data;
  const error =
    runQuery.error instanceof Error
      ? runQuery.error.message
      : runQuery.error
        ? errorDetail(runQuery.error)
        : null;

  function handleRun() {
    runQuery.mutate({ sql, row_limit: 1000, timeout_seconds: 30 });
  }

  async function handleSave() {
    const trimmed = saveName.trim();
    if (!trimmed) return;
    try {
      await createSaved.mutateAsync({ name: trimmed, sql });
      setSaveName("");
      toast.success("Saved", { description: trimmed });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : errorDetail(err);
      toast.error("Could not save", { description: msg });
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">SQL</h1>
        <p className="text-xs text-muted-foreground">
          Read-only. SELECT / WITH / SHOW / DESCRIBE / EXPLAIN.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <SqlEditor value={sql} onChange={setSql} onSubmit={handleRun} />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={handleRun}
              disabled={runQuery.isPending}
              size="sm"
            >
              {runQuery.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run
            </Button>
            <div className="flex items-center gap-1">
              <Input
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="name to save…"
                className="h-8 w-44 text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={handleSave}
                disabled={!saveName.trim() || createSaved.isPending}
              >
                <Save className="h-3.5 w-3.5" /> Save
              </Button>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button
                size="sm"
                variant={panel === "saved" ? "default" : "ghost"}
                onClick={() => setPanel(panel === "saved" ? null : "saved")}
              >
                <Bookmark className="h-3.5 w-3.5" /> Saved (
                {saved.data?.total ?? 0})
              </Button>
              <Button
                size="sm"
                variant={panel === "history" ? "default" : "ghost"}
                onClick={() => setPanel(panel === "history" ? null : "history")}
              >
                <History className="h-3.5 w-3.5" /> History
              </Button>
            </div>
          </div>
          <StatusRow
            isPending={runQuery.isPending}
            result={result ?? null}
            error={error}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardContent className="p-0">
            {error ? (
              <pre className="overflow-x-auto rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                {error}
              </pre>
            ) : result ? (
              <ResultsGrid result={result} />
            ) : (
              <div className="p-6">
                <EmptyState
                  icon={<Play className="h-8 w-8" />}
                  title="Run a query"
                  description="Press Cmd/Ctrl + Enter or click Run to execute."
                />
              </div>
            )}
          </CardContent>
        </Card>

        {panel === "saved" ? (
          <SavedPanel
            items={saved.data?.items ?? []}
            isLoading={saved.isLoading}
            onPick={(s) => {
              setSql(s);
              setPanel(null);
            }}
            onDelete={async (id) => {
              try {
                await deleteSaved.mutateAsync(id);
              } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : errorDetail(err);
                toast.error("Delete failed", { description: msg });
              }
            }}
            onClose={() => setPanel(null)}
          />
        ) : null}

        {panel === "history" ? (
          <HistoryPanel
            items={history.data?.items ?? []}
            isLoading={history.isLoading}
            onPick={(s) => {
              setSql(s);
              setPanel(null);
            }}
            onClose={() => setPanel(null)}
          />
        ) : null}
      </div>
    </div>
  );
}

function StatusRow({
  isPending,
  result,
  error,
}: {
  isPending: boolean;
  result: { row_count: number; truncated: boolean; duration_ms: number } | null;
  error: string | null;
}) {
  if (isPending) {
    return (
      <p className="text-xs text-muted-foreground">
        <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" /> running…
      </p>
    );
  }
  if (error) {
    return <p className="text-xs text-destructive">error</p>;
  }
  if (!result) return <p className="text-xs text-muted-foreground">idle</p>;
  return (
    <p className="text-xs text-muted-foreground">
      {result.row_count.toLocaleString()} row
      {result.row_count === 1 ? "" : "s"}
      {result.truncated ? " (truncated)" : ""} · {formatDuration(result.duration_ms / 1000)}
    </p>
  );
}

function SavedPanel({
  items,
  isLoading,
  onPick,
  onDelete,
  onClose,
}: {
  items: { id: string; name: string; sql: string }[];
  isLoading: boolean;
  onPick: (sql: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Saved
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close panel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        {isLoading ? (
          <p className="px-3 py-4 text-xs text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-3 py-4 text-xs text-muted-foreground">
            No saved queries yet.
          </p>
        ) : (
          <ul className="max-h-[420px] overflow-auto">
            {items.map((item) => (
              <li
                key={item.id}
                className="group flex items-start gap-2 border-b px-3 py-2 last:border-0 hover:bg-muted/30"
              >
                <button
                  type="button"
                  onClick={() => onPick(item.sql)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="text-sm font-medium">{item.name}</div>
                  <div className="truncate font-mono text-xs text-muted-foreground">
                    {item.sql}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(item.id)}
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                  aria-label={`Delete ${item.name}`}
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function HistoryPanel({
  items,
  isLoading,
  onPick,
  onClose,
}: {
  items: {
    id: number;
    sql: string;
    executed_at: string;
    duration_ms: number;
    row_count: number | null;
    error_message: string | null;
  }[];
  isLoading: boolean;
  onPick: (sql: string) => void;
  onClose: () => void;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            History
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close panel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        {isLoading ? (
          <p className="px-3 py-4 text-xs text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <p className="px-3 py-4 text-xs text-muted-foreground">No queries yet.</p>
        ) : (
          <ul className="max-h-[420px] overflow-auto">
            {items.map((item) => (
              <li
                key={item.id}
                className="border-b px-3 py-2 last:border-0 hover:bg-muted/30"
              >
                <button
                  type="button"
                  onClick={() => onPick(item.sql)}
                  className="block w-full text-left"
                >
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-wide text-muted-foreground">
                    <span>{formatRelativeTime(item.executed_at)}</span>
                    <span>·</span>
                    <span>{formatDuration(item.duration_ms / 1000)}</span>
                    {item.error_message ? (
                      <span className="text-destructive">error</span>
                    ) : item.row_count !== null ? (
                      <span>{item.row_count} rows</span>
                    ) : null}
                  </div>
                  <div className="truncate font-mono text-xs">{item.sql}</div>
                  {item.error_message ? (
                    <div className="truncate text-xs text-destructive">
                      {item.error_message}
                    </div>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function errorDetail(err: unknown): string {
  if (!err) return "unknown error";
  if (typeof err === "string") return err;
  if (typeof err === "object" && err !== null) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return String(err);
}
