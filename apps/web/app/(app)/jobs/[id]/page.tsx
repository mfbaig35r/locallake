"use client";

import { ChevronLeft, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCancelJob, useJob } from "@/lib/api/hooks";
import { formatDuration, formatRelativeTime } from "@/lib/utils";

const TERMINAL = new Set(["success", "failed", "cancelled", "timed_out"]);

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useJob(id);
  const cancel = useCancelJob();

  async function handleCancel() {
    try {
      await cancel.mutateAsync(id);
      toast.success("Cancellation requested");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "cancel failed";
      toast.error("Could not cancel", { description: msg });
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
          href="/jobs"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Runs
        </Link>
        <p className="text-sm">Job not found.</p>
      </div>
    );
  }

  const params = JSON.parse(data.parameters_json || "{}") as Record<string, unknown>;
  const canCancel = !TERMINAL.has(data.status) && data.status !== "running";

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Runs
        </Link>
        <div className="mt-2 flex items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-mono text-lg font-semibold tracking-tight">
              {data.notebook_path}
            </h1>
            <p className="truncate font-mono text-xs text-muted-foreground">
              {data.id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={data.status} />
            {canCancel ? (
              <Button
                size="sm"
                variant="outline"
                onClick={handleCancel}
                disabled={cancel.isPending}
              >
                <X className="h-3.5 w-3.5" /> Cancel
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Timing</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
          <Meta label="Created" value={formatRelativeTime(data.created_at)} />
          <Meta label="Started" value={formatRelativeTime(data.started_at)} />
          <Meta label="Finished" value={formatRelativeTime(data.finished_at)} />
          <Meta label="Duration" value={formatDuration(data.duration_seconds)} />
          <Meta label="Triggered" value={data.triggered_by} />
          <Meta
            label="Git SHA"
            value={data.git_commit_sha ? data.git_commit_sha.slice(0, 8) : "—"}
            mono
          />
          <Meta label="Dirty" value={data.git_dirty ? "yes" : "no"} />
          <Meta label="Timeout" value={`${data.timeout_seconds}s`} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Parameters</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(params).length === 0 ? (
              <p className="text-sm text-muted-foreground">No parameters.</p>
            ) : (
              <pre className="overflow-x-auto rounded-md bg-muted/40 p-3 text-xs">
                {JSON.stringify(params, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Outputs</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              <Row label="MCP run ID" value={data.mcp_run_id ?? "—"} mono />
              <Row label="Artifacts" value={data.artifact_path ?? "—"} mono />
              <Row label="Log file" value={data.log_path ?? "—"} mono />
            </dl>
          </CardContent>
        </Card>
      </div>

      {data.error_message ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-md bg-destructive/10 p-3 text-xs text-destructive">
              {data.error_message}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Live log streaming + artifact preview land in Phase 3.
      </p>
    </div>
  );
}

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={mono ? "mt-1 font-mono text-xs" : "mt-1 text-sm"}>{value}</div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={
          mono
            ? "min-w-0 flex-1 truncate text-right font-mono text-xs"
            : "min-w-0 flex-1 truncate text-right text-sm"
        }
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
