import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
  {
    variants: {
      tone: {
        neutral: "bg-muted text-muted-foreground ring-border",
        info: "bg-info/15 text-info ring-info/30",
        success: "bg-success/15 text-success ring-success/30",
        warning: "bg-warning/15 text-warning ring-warning/30",
        destructive: "bg-destructive/15 text-destructive ring-destructive/30",
        primary: "bg-primary/15 text-primary ring-primary/30",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone, className }))} {...props} />;
}
