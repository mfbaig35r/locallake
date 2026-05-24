"use client";

import { Database, Loader2, Table2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useCatalogTables, type TableEntry } from "@/lib/api/hooks";

export default function CatalogPage() {
  const { data, isLoading } = useCatalogTables();
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const items = data?.items ?? [];
    const q = query.trim().toLowerCase();
    const filtered = q
      ? items.filter(
          (it) =>
            it.name.toLowerCase().includes(q) ||
            it.schema.toLowerCase().includes(q)
        )
      : items;
    const map = new Map<string, TableEntry[]>();
    for (const it of filtered) {
      const bucket = map.get(it.schema) ?? [];
      bucket.push(it);
      map.set(it.schema, bucket);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data, query]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Catalog</h1>
          <p className="text-xs text-muted-foreground">
            Tables and views in the workspace database.
          </p>
        </div>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter…"
          className="h-8 w-56 text-sm"
        />
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading catalog…
        </div>
      ) : grouped.length === 0 ? (
        <EmptyState
          icon={<Database className="h-8 w-8" />}
          title={query ? "No matches" : "No tables yet"}
          description={
            query
              ? "Try a different filter."
              : "Create a table by running a notebook that calls __lake__.connection()."
          }
        />
      ) : (
        <div className="space-y-4">
          {grouped.map(([schema, items]) => (
            <Card key={schema}>
              <CardContent className="pt-4">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {schema}
                </div>
                <ul className="divide-y">
                  {items.map((it) => (
                    <li key={`${it.schema}.${it.name}`}>
                      <Link
                        href={`/catalog/${encodeURIComponent(it.schema)}/${encodeURIComponent(it.name)}`}
                        className="flex items-center gap-2 py-2 text-sm hover:text-foreground"
                      >
                        <Table2 className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-mono">{it.name}</span>
                        <span className="ml-auto text-xs uppercase tracking-wide text-muted-foreground">
                          {it.kind}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
