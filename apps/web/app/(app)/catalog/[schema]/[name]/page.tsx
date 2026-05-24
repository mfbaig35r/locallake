"use client";

import { ChevronLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTableDetail } from "@/lib/api/hooks";

export default function TableDetailPage() {
  const params = useParams<{ schema: string; name: string }>();
  const schema = decodeURIComponent(params.schema);
  const name = decodeURIComponent(params.name);
  const { data, isLoading, error } = useTableDetail(schema, name);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading table…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="space-y-3">
        <BackLink />
        <p className="text-sm text-destructive">Table not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <BackLink />
        <div className="mt-2 flex items-end justify-between gap-4">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              {schema}
            </div>
            <h1 className="font-mono text-lg font-semibold tracking-tight">
              {name}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="uppercase tracking-wide">{data.kind}</span>
            {data.row_count != null ? (
              <span>{data.row_count.toLocaleString()} rows</span>
            ) : null}
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Schema</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Column</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="w-24">Nullable</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.columns.map((c) => (
                <TableRow key={c.name}>
                  <TableCell className="font-mono text-xs">{c.name}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {c.type}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {c.nullable ? "yes" : "no"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sample</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {data.sample_rows.length === 0 ? (
            <p className="px-3 py-6 text-sm text-muted-foreground">
              Empty table.
            </p>
          ) : (
            <div className="overflow-auto">
              <table className="w-full border-collapse text-xs">
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b">
                    {data.sample_columns.map((c) => (
                      <th
                        key={c}
                        className="whitespace-nowrap px-3 py-2 text-left font-mono font-medium text-muted-foreground"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.sample_rows.map((row, i) => (
                    <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                      {(row as unknown[]).map((cell, j) => (
                        <td key={j} className="whitespace-nowrap px-3 py-1.5 font-mono">
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/catalog"
      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
    >
      <ChevronLeft className="h-3.5 w-3.5" /> Catalog
    </Link>
  );
}
