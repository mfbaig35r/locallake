"use client";

import type { QueryResult } from "@/lib/api/hooks";

export function ResultsGrid({ result }: { result: QueryResult }) {
  if (result.columns.length === 0) {
    return (
      <div className="px-3 py-6 text-sm text-muted-foreground">
        Query returned no columns.
      </div>
    );
  }
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b">
            {result.columns.map((c) => (
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
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
              {(row as unknown[]).map((cell, j) => (
                <td key={j} className="whitespace-nowrap px-3 py-1.5 font-mono">
                  {cell === null ? (
                    <span className="text-muted-foreground/60">null</span>
                  ) : typeof cell === "boolean" ? (
                    String(cell)
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
