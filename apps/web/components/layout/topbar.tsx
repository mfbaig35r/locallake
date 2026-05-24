"use client";

import { Activity, Circle, GitBranch } from "lucide-react";
import { useGitStatus, useHealth } from "@/lib/api/hooks";

export function Topbar() {
  const { data, isError } = useHealth();
  const git = useGitStatus();
  const ok = !!data && !isError;
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-medium text-muted-foreground">Workspace</h1>
        <span className="text-sm font-semibold">my-locallake</span>
      </div>
      <div className="flex items-center gap-4 text-xs">
        <GitPill status={git.data} />
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

function GitPill({
  status,
}: {
  status:
    | {
        is_repo: boolean;
        branch: string | null;
        dirty: boolean;
        ahead: number;
        behind: number;
      }
    | undefined;
}) {
  if (!status || !status.is_repo) return null;
  const aheadBehind: string[] = [];
  if (status.ahead) aheadBehind.push(`↑${status.ahead}`);
  if (status.behind) aheadBehind.push(`↓${status.behind}`);
  return (
    <div className="flex items-center gap-1.5 text-muted-foreground">
      <GitBranch className="h-3.5 w-3.5" />
      <span className="font-mono">{status.branch ?? "detached"}</span>
      {status.dirty ? (
        <span
          className="rounded-sm bg-amber-500/15 px-1 py-0.5 text-[10px] font-medium text-amber-500"
          title="Working tree has uncommitted changes"
        >
          dirty
        </span>
      ) : null}
      {aheadBehind.length > 0 ? (
        <span className="text-[10px] text-muted-foreground/70">
          {aheadBehind.join(" ")}
        </span>
      ) : null}
    </div>
  );
}
