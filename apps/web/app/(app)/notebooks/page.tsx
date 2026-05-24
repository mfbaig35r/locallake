"use client";

import { FileCode2, Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useNotebooks, useRunNotebook, type NotebookEntry } from "@/lib/api/hooks";
import { formatBytes, formatRelativeTime } from "@/lib/utils";

export default function NotebooksPage() {
  const { data, isLoading } = useNotebooks();
  const [query, setQuery] = useState("");
  const router = useRouter();
  const run = useRunNotebook();

  const items: NotebookEntry[] = (data?.items ?? []).filter((nb) =>
    nb.path.toLowerCase().includes(query.toLowerCase())
  );

  async function handleRun(path: string) {
    try {
      const job = await run.mutateAsync({ path });
      toast.success("Job queued", { description: path });
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "submission failed";
      toast.error("Could not queue notebook", { description: msg });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Notebooks</h1>
          <p className="text-sm text-muted-foreground">
            Marimo notebooks in <code className="text-xs">workspace/notebooks</code>.
          </p>
        </div>
        <Input
          placeholder="Filter…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-60"
        />
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<FileCode2 className="h-8 w-8" />}
          title={query ? "No matches" : "No notebooks yet"}
          description={
            query
              ? "Try a different filter."
              : "Add a .py marimo file to your workspace notebooks directory."
          }
        />
      ) : (
        <div className="rounded-lg border border-border bg-card/40">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Path</TableHead>
                <TableHead className="w-32">Size</TableHead>
                <TableHead className="w-36">Modified</TableHead>
                <TableHead className="w-28 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((nb) => (
                <TableRow key={nb.path}>
                  <TableCell className="font-mono text-xs">
                    <Link
                      href={`/notebooks/${nb.path}`}
                      className="hover:underline"
                    >
                      {nb.path}
                    </Link>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatBytes(nb.size_bytes)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatRelativeTime(nb.last_modified)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRun(nb.path)}
                      disabled={run.isPending}
                    >
                      <Play className="h-3.5 w-3.5" /> Run
                    </Button>
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
