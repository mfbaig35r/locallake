"use client";

import {
  ChevronDown,
  ChevronRight,
  Download,
  File,
  FileBarChart,
  FileJson,
  FileText,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";
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
import { api } from "@/lib/api/client";
import { useArtifacts, type ArtifactEntry, type ArtifactPreview } from "@/lib/api/hooks";
import { formatBytes } from "@/lib/utils";

export function ArtifactsList({ jobId }: { jobId: string }) {
  const { data, isLoading, error } = useArtifacts(jobId);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading artifacts…
      </div>
    );
  }
  if (error) {
    return <p className="text-sm text-destructive">Failed to load artifacts.</p>;
  }
  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        icon={<File className="h-8 w-8" />}
        title="No artifacts yet"
        description="Files saved via __lake__.save_artifact() will appear here."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8" />
          <TableHead>File</TableHead>
          <TableHead className="w-32 text-right">Size</TableHead>
          <TableHead className="w-24 text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((item) => {
          const isOpen = expanded === item.path;
          return (
            <Row
              key={item.path}
              jobId={jobId}
              item={item}
              isOpen={isOpen}
              onToggle={() => setExpanded(isOpen ? null : item.path)}
            />
          );
        })}
      </TableBody>
    </Table>
  );
}

function Row({
  jobId,
  item,
  isOpen,
  onToggle,
}: {
  jobId: string;
  item: ArtifactEntry;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <TableRow>
        <TableCell>
          {item.previewable ? (
            <button
              type="button"
              onClick={onToggle}
              className="text-muted-foreground hover:text-foreground"
              aria-label={isOpen ? "Collapse preview" : "Expand preview"}
            >
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          ) : null}
        </TableCell>
        <TableCell className="font-mono text-xs">
          <span className="inline-flex items-center gap-2">
            <FileIcon path={item.path} />
            {item.path}
          </span>
        </TableCell>
        <TableCell className="text-right text-xs text-muted-foreground">
          {formatBytes(item.size_bytes)}
        </TableCell>
        <TableCell className="text-right">
          <a
            href={downloadUrl(jobId, item.path)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Download className="h-3.5 w-3.5" /> Download
          </a>
        </TableCell>
      </TableRow>
      {isOpen ? (
        <TableRow>
          <TableCell colSpan={4} className="bg-muted/20 p-0">
            <ParquetPreview jobId={jobId} path={item.path} />
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

function ParquetPreview({ jobId, path }: { jobId: string; path: string }) {
  const [data, setData] = useState<ArtifactPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.GET(
          "/jobs/{job_id}/artifacts/{artifact_path}/preview",
          {
            params: {
              path: { job_id: jobId, artifact_path: path },
              query: { rows: 50 },
            },
          }
        );
        if (cancelled) return;
        const errVal = (res as { error?: unknown }).error;
        if (errVal) {
          const detail = (errVal as { detail?: unknown }).detail;
          setError(
            typeof detail === "string"
              ? detail
              : typeof errVal === "string"
                ? errVal
                : "preview failed"
          );
        } else {
          setData(res.data as ArtifactPreview);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "preview failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId, path]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-4 py-6 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading parquet…
      </div>
    );
  }
  if (error) {
    return <p className="px-4 py-3 text-xs text-destructive">{error}</p>;
  }
  if (!data) return null;

  return (
    <div className="overflow-x-auto px-4 py-3">
      <div className="mb-2 text-xs text-muted-foreground">
        {data.total_rows.toLocaleString()} rows · showing {data.rows.length}
        {data.truncated ? " (truncated)" : ""}
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-left">
            {data.columns.map((c) => (
              <th key={c} className="px-2 py-1 font-mono font-medium text-muted-foreground">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className="border-b last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1 font-mono">
                  {cell === null ? (
                    <span className="text-muted-foreground/60">null</span>
                  ) : (
                    String(cell)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FileIcon({ path }: { path: string }) {
  const ext = path.toLowerCase().split(".").pop() ?? "";
  if (ext === "parquet") return <FileBarChart className="h-3.5 w-3.5 text-violet-400" />;
  if (ext === "json") return <FileJson className="h-3.5 w-3.5 text-amber-400" />;
  if (ext === "csv" || ext === "tsv") return <FileText className="h-3.5 w-3.5 text-emerald-400" />;
  return <File className="h-3.5 w-3.5 text-muted-foreground" />;
}

function downloadUrl(jobId: string, path: string): string {
  if (typeof window === "undefined") return "";
  const explicit = process.env.NEXT_PUBLIC_API_URL;
  const base = explicit ?? window.location.origin.replace(":3000", ":8000");
  return `${base}/jobs/${encodeURIComponent(jobId)}/artifacts/${path
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}
