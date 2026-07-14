import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary/10 text-primary",
        secondary: "bg-secondary text-secondary-foreground",
        destructive: "bg-danger/10 text-danger",
        outline: "border border-input text-foreground",
        success: "bg-success/10 text-success",
        warning: "bg-warning/10 text-warning",
        purple: "bg-[#7C3AED]/10 text-[#7C3AED] dark:bg-[#7C3AED]/20 dark:text-purple-300",
        blue: "bg-[#2E75B6]/10 text-[#2E75B6] dark:bg-[#2E75B6]/20 dark:text-blue-300",
        neutral: "bg-neutral-500/10 text-neutral-500 dark:bg-neutral-600/20 dark:text-neutral-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
