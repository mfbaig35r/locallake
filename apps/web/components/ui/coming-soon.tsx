import { EmptyState } from "@/components/ui/empty-state";

export function ComingSoon({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      </div>
      <EmptyState
        title={`${title} lands in ${phase}`}
        description="See PLAN.md for the full roadmap."
      />
    </div>
  );
}
