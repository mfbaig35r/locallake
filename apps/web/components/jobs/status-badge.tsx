import { Badge } from "@/components/ui/badge";

const TONE = {
  queued: "neutral",
  running: "info",
  success: "success",
  failed: "destructive",
  cancelled: "warning",
  timed_out: "warning",
} as const;

const LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  success: "Success",
  failed: "Failed",
  cancelled: "Cancelled",
  timed_out: "Timed out",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONE[status as keyof typeof TONE] ?? "neutral";
  return <Badge tone={tone}>{LABEL[status] ?? status}</Badge>;
}
