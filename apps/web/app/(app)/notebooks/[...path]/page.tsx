"use client";

import { ChevronLeft, Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useNotebook, useRunNotebook } from "@/lib/api/hooks";
import { formatBytes, formatDuration, formatRelativeTime } from "@/lib/utils";

export default function NotebookDetailPage() {
  const params = useParams<{ path: string[] }>();
  const router = useRouter();
  const notebookPath = (params.path ?? []).map(decodeURIComponent).join("/");
  const { data, isLoading, error } = useNotebook(notebookPath);
  const run = useRunNotebook();

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
          <Button onClick={handleRun} disabled={run.isPending}>
            <Play className="h-4 w-4" /> Run
          </Button>
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
