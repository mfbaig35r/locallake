"use client";

import { FileCode2, ListChecks } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/jobs/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useJobs, useNotebooks } from "@/lib/api/hooks";
import { formatRelativeTime } from "@/lib/utils";

export default function DashboardPage() {
  const jobs = useJobs({ limit: 5 });
  const notebooks = useNotebooks();
  const recentNotebooks = (notebooks.data?.items ?? [])
    .slice()
    .sort((a, b) => +new Date(b.last_modified) - +new Date(a.last_modified))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          A quick view of recent activity in your workspace.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent runs</CardTitle>
            <Link
              href="/jobs"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all →
            </Link>
          </CardHeader>
          <CardContent>
            {jobs.data && jobs.data.items.length === 0 ? (
              <EmptyState
                icon={<ListChecks className="h-7 w-7" />}
                title="No runs yet"
                description="Run a notebook from the Notebooks page to see it here."
              />
            ) : (
              <ul className="space-y-2">
                {(jobs.data?.items ?? []).map((j) => (
                  <li key={j.id} className="flex items-center justify-between gap-3">
                    <Link
                      href={`/jobs/${j.id}`}
                      className="min-w-0 flex-1 truncate text-sm hover:underline"
                      title={j.notebook_path}
                    >
                      {j.notebook_path}
                    </Link>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(j.created_at)}
                    </span>
                    <StatusBadge status={j.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent notebooks</CardTitle>
            <Link
              href="/notebooks"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all →
            </Link>
          </CardHeader>
          <CardContent>
            {recentNotebooks.length === 0 ? (
              <EmptyState
                icon={<FileCode2 className="h-7 w-7" />}
                title="No notebooks yet"
                description="Open Notebooks and click New to start from a template."
              />
            ) : (
              <ul className="space-y-2">
                {recentNotebooks.map((nb) => (
                  <li key={nb.path} className="flex items-center justify-between gap-3">
                    <Link
                      href={`/notebooks/${nb.path}`}
                      className="min-w-0 flex-1 truncate text-sm hover:underline"
                      title={nb.path}
                    >
                      {nb.path}
                    </Link>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatRelativeTime(nb.last_modified)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
