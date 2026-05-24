"use client";

import {
  CalendarClock,
  Database,
  FileCode2,
  LayoutDashboard,
  ListChecks,
  Settings,
  TerminalSquare,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/notebooks", label: "Notebooks", icon: FileCode2 },
  { href: "/jobs", label: "Runs", icon: ListChecks },
  { href: "/sql", label: "SQL", icon: TerminalSquare },
  { href: "/catalog", label: "Catalog", icon: Database },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card/40">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="h-2 w-2 rounded-full bg-primary" />
        <span className="text-sm font-semibold tracking-tight">LocalLake</span>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            path === href || (href !== "/" && path.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3 text-xs text-muted-foreground">
        Phase 2 — UI shell
      </div>
    </aside>
  );
}
