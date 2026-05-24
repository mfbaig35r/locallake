"use client";

import { ListChecks, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useJobs } from "@/lib/api/hooks";
import { cn, formatDuration, formatRelativeTime } from "@/lib/utils";

const STATUSES = [
  { value: undefined, label: "All" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "success", label: "Success" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const TRIGGERS = [
  { value: undefined, label: "Any" },
  { value: "ui", label: "UI" },
  { value: "api", label: "API" },
  { value: "schedule", label: "Schedule" },
];

const SINCE_PRESETS: { label: string; hours: number | null }[] = [
  { label: "All time", hours: null },
  { label: "1h", hours: 1 },
  { label: "24h", hours: 24 },
  { label: "7d", hours: 24 * 7 },
];

function computeSince(hours: number | null): string | undefined {
  if (hours == null) return undefined;
  return new Date(Date.now() - hours * 3600 * 1000).toISOString();
}

function JobsContent() {
  const search = useSearchParams();
  const initial = search.get("status") ?? undefined;
  const [status, setStatus] = useState<string | undefined>(initial);
  const [triggeredBy, setTriggeredBy] = useState<string | undefined>();
  const [sinceHours, setSinceHours] = useState<number | null>(null);
  const since = computeSince(sinceHours);
  const { data, isLoading } = useJobs({
    status,
    triggeredBy,
    since,
    limit: 100,
  });
  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
        <p className="text-sm text-muted-foreground">
          Job history. Active runs poll every 3 seconds.
        </p>
      </div>

      <div className="space-y-2">
        <FilterRow label="Status">
          {STATUSES.map((s) => (
            <Button
              key={s.label}
              size="sm"
              variant={status === s.value ? "default" : "outline"}
              onClick={() => setStatus(s.value)}
              className={cn(status === s.value ? "" : "text-muted-foreground")}
            >
              {s.label}
            </Button>
          ))}
        </FilterRow>
        <FilterRow label="Triggered by">
          {TRIGGERS.map((t) => (
            <Button
              key={t.label}
              size="sm"
              variant={triggeredBy === t.value ? "default" : "outline"}
              onClick={() => setTriggeredBy(t.value)}
              className={cn(
                triggeredBy === t.value ? "" : "text-muted-foreground"
              )}
            >
              {t.label}
            </Button>
          ))}
        </FilterRow>
        <FilterRow label="Since">
          {SINCE_PRESETS.map((s) => (
            <Button
              key={s.label}
              size="sm"
              variant={sinceHours === s.hours ? "default" : "outline"}
              onClick={() => setSinceHours(s.hours)}
              className={cn(
                sinceHours === s.hours ? "" : "text-muted-foreground"
              )}
            >
              {s.label}
            </Button>
          ))}
        </FilterRow>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<ListChecks className="h-8 w-8" />}
          title="No runs"
          description={
            status ? `No jobs with status "${status}".` : "Run a notebook to see history here."
          }
        />
      ) : (
        <div className="rounded-lg border border-border bg-card/40">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Notebook</TableHead>
                <TableHead className="w-32">Status</TableHead>
                <TableHead className="w-32">Created</TableHead>
                <TableHead className="w-28">Duration</TableHead>
                <TableHead className="w-28">Triggered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((j) => (
                <TableRow key={j.id}>
                  <TableCell className="font-mono text-xs">
                    <Link href={`/jobs/${j.id}`} className="hover:underline">
                      {j.notebook_path}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={j.status} />
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatRelativeTime(j.created_at)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDuration(j.duration_seconds)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {j.triggered_by}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 w-20 text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      }
    >
      <JobsContent />
    </Suspense>
  );
}
