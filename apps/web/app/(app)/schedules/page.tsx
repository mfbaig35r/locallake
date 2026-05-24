"use client";

import { CalendarClock, Loader2, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { NewScheduleModal } from "@/components/schedules/new-schedule-modal";
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
import {
  useDeleteSchedule,
  useSchedules,
  useUpdateSchedule,
} from "@/lib/api/hooks";
import { formatRelativeTime } from "@/lib/utils";

export default function SchedulesPage() {
  const { data, isLoading } = useSchedules();
  const update = useUpdateSchedule();
  const remove = useDeleteSchedule();
  const [newOpen, setNewOpen] = useState(false);

  const items = data?.items ?? [];

  async function handleToggle(id: string, next: boolean) {
    try {
      await update.mutateAsync({ id, body: { enabled: next } });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "toggle failed";
      toast.error("Could not update", { description: msg });
    }
  }

  async function handleDelete(id: string, label: string) {
    if (!confirm(`Delete schedule for ${label}?`)) return;
    try {
      await remove.mutateAsync(id);
      toast.success("Deleted", { description: label });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "delete failed";
      toast.error("Could not delete", { description: msg });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Schedules</h1>
          <p className="text-xs text-muted-foreground">
            Cron-driven notebook runs. UTC. Edits take effect on the worker's next tick (≤60s).
          </p>
        </div>
        <Button size="sm" onClick={() => setNewOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> New
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<CalendarClock className="h-8 w-8" />}
          title="No schedules yet"
          description="Schedule a notebook to run on a cron."
          action={
            <Button size="sm" onClick={() => setNewOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> New schedule
            </Button>
          }
        />
      ) : (
        <div className="rounded-lg border border-border bg-card/40">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Notebook</TableHead>
                <TableHead className="w-32">Cron</TableHead>
                <TableHead className="w-40">Next fire (UTC)</TableHead>
                <TableHead className="w-32">Last run</TableHead>
                <TableHead className="w-20">Retries</TableHead>
                <TableHead className="w-20">Enabled</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((sched) => (
                <TableRow key={sched.id}>
                  <TableCell className="font-mono text-xs">
                    <Link
                      href={`/notebooks/${sched.notebook_path}`}
                      className="hover:underline"
                    >
                      {sched.notebook_path}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {sched.cron_expression}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {sched.next_fire_at
                      ? new Date(sched.next_fire_at).toISOString().replace("T", " ").slice(0, 16)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {sched.last_run_id ? (
                      <Link
                        href={`/jobs/${sched.last_run_id}`}
                        className="text-muted-foreground hover:underline"
                      >
                        {formatRelativeTime(sched.last_run_at)}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {sched.max_retries}
                  </TableCell>
                  <TableCell>
                    <label className="inline-flex cursor-pointer items-center">
                      <input
                        type="checkbox"
                        checked={sched.enabled}
                        onChange={(e) => handleToggle(sched.id, e.target.checked)}
                        className="h-3.5 w-3.5"
                      />
                    </label>
                  </TableCell>
                  <TableCell className="text-right">
                    <button
                      type="button"
                      onClick={() => handleDelete(sched.id, sched.notebook_path)}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label={`Delete schedule for ${sched.notebook_path}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <NewScheduleModal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        onCreated={() => toast.success("Schedule created")}
      />
    </div>
  );
}
