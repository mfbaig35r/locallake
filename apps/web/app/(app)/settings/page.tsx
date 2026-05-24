"use client";

import { Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/lib/api/hooks";

export default function SettingsPage() {
  const { data, isLoading, error } = useWorkspace();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading workspace…
      </div>
    );
  }
  if (error || !data) {
    return <p className="text-sm text-destructive">Failed to load workspace.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-xs text-muted-foreground">
          Read-only. Edit <code>config/workspace.yaml</code> directly and restart the API + worker to apply changes.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Workspace</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Row label="Name" value={data.name} />
            <Row label="Root" value={data.root_path} mono />
            <Row label="DuckDB" value={data.database_path} mono />
            <Row label="Metadata DB" value={data.metadata_db_path} mono />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Paths</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Row label="Notebooks" value={data.paths.notebooks} mono />
            <Row label="Artifacts" value={data.paths.artifacts} mono />
            <Row label="Logs" value={data.paths.logs} mono />
            <Row label="Templates" value={data.paths.templates} mono />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Worker</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Row
              label="Concurrency"
              value={`${data.worker_concurrency} (set via LOCALLAKE_WORKER_CONCURRENCY)`}
            />
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Increase concurrency to run multiple notebooks in parallel. Each worker
            spawns its own marimo-sandbox subprocess; higher values mean more memory
            usage per node.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={mono ? "mt-1 truncate font-mono text-xs" : "mt-1 truncate text-sm"}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
