import { cn } from "@/lib/utils";

type BadgeVariant = "brand" | "success" | "warning" | "danger" | "neutral" | "info";

const variantStyles: Record<BadgeVariant, string> = {
  brand: "bg-sky-100 text-sky-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
  neutral: "bg-neutral-100 text-neutral-600",
  info: "bg-blue-100 text-blue-700",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "neutral", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
