"use client";

import { Activity, Circle } from "lucide-react";
import { useHealth } from "@/lib/api/hooks";

export function Topbar() {
  const { data, isError } = useHealth();
  const ok = !!data && !isError;
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-medium text-muted-foreground">Workspace</h1>
        <span className="text-sm font-semibold">my-locallake</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Activity className="h-3.5 w-3.5" />
          API
          <Circle
            className={
              ok
                ? "h-2 w-2 fill-success text-success"
                : "h-2 w-2 fill-destructive text-destructive"
            }
          />
          <span>{ok ? "ok" : "down"}</span>
        </div>
      </div>
    </header>
  );
}
