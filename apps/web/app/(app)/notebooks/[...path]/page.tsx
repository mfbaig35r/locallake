"use client";

import {
  CalendarClock,
  ChevronLeft,
  ExternalLink,
  Loader2,
  Pencil,
  Play,
  Square,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { StatusBadge } from "@/components/jobs/status-badge";
import { NewScheduleModal } from "@/components/schedules/new-schedule-modal";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useMarimoSession,
  useNotebook,
  useOpenInMarimo,
  useRunNotebook,
  useStopMarimo,
} from "@/lib/api/hooks";
import { formatBytes, formatDuration, formatRelativeTime } from "@/lib/utils";

export default function NotebookDetailPage() {
  const params = useParams<{ path: string[] }>();
  const router = useRouter();
  const notebookPath = (params.path ?? []).map(decodeURIComponent).join("/");
  const { data, isLoading, error } = useNotebook(notebookPath);
  const run = useRunNotebook();
  const marimoSession = useMarimoSession(notebookPath);
  const openMarimo = useOpenInMarimo();
  const stopMarimo = useStopMarimo();
  const [scheduleOpen, setScheduleOpen] = useState(false);

  async function handleOpenInMarimo() {
    try {
      const sess = await openMarimo.mutateAsync(notebookPath);
      window.open(sess.url, "_blank", "noopener");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "open failed";
      toast.error("Could not start marimo", { description: msg });
    }
  }

  async function handleStopMarimo() {
    try {
      await stopMarimo.mutateAsync(notebookPath);
      toast.success("Marimo session stopped");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "stop failed";
      toast.error("Could not stop", { description: msg });
    }
  }

  async function handleRun() {
    try {
      const job = await run.mutateAsync({ path: notebookPath });
      toast.success("Job queued");
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "submission failed";
      toast.error("Could not queue notebook", { description: msg });
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-3">
        <Link
          href="/notebooks"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Notebooks
        </Link>
        <EmptyState title="Notebook not found" description={notebookPath} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/notebooks"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Notebooks
        </Link>
        <div className="mt-2 flex items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-mono text-xl font-semibold tracking-tight">
              {data.name}
            </h1>
            <p className="truncate text-sm text-muted-foreground">{data.path}</p>
          </div>
          <div className="flex items-center gap-2">
            {marimoSession.data ? (
              <>
                <a
                  href={marimoSession.data.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-9 items-center gap-1.5 rounded-md border border-emerald-600/30 bg-emerald-600/10 px-3 text-xs font-medium text-emerald-700 hover:bg-emerald-600/20"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Open editor
                </a>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStopMarimo}
                  disabled={stopMarimo.isPending}
                >
                  <Square className="h-3 w-3" /> Stop
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                onClick={handleOpenInMarimo}
                disabled={openMarimo.isPending}
              >
                {openMarimo.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Pencil className="h-3.5 w-3.5" />
                )}
                Edit in marimo
              </Button>
            )}
            <Button variant="outline" onClick={() => setScheduleOpen(true)}>
              <CalendarClock className="h-3.5 w-3.5" /> Schedule
            </Button>
            <Button onClick={handleRun} disabled={run.isPending}>
              <Play className="h-4 w-4" /> Run
            </Button>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
          <Meta label="Size" value={formatBytes(data.size_bytes)} />
          <Meta label="Modified" value={formatRelativeTime(data.last_modified)} />
          <Meta label="Path" value={data.path} mono />
          <Meta label="Recent runs" value={String(data.recent_runs.length)} />
        </CardContent>
      </Card>

      <NewScheduleModal
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        initialNotebookPath={notebookPath}
        onCreated={() => {
          toast.success("Schedule created");
          router.push("/schedules");
        }}
      />

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_runs.length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Click Run above to submit this notebook."
            />
          ) : (
            <ul className="divide-y divide-border">
              {data.recent_runs.map((r) => (
                <li key={r.id} className="flex items-center gap-3 py-2.5">
                  <Link
                    href={`/jobs/${r.id}`}
                    className="min-w-0 flex-1 truncate font-mono text-xs hover:underline"
                  >
                    {r.id}
                  </Link>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(r.created_at)}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatDuration(r.duration_seconds)}
                  </span>
                  <StatusBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={
          mono ? "mt-1 truncate font-mono text-xs" : "mt-1 truncate text-sm"
        }
        title={value}
      >
        {value}
      </div>
    </div>
  );
}
