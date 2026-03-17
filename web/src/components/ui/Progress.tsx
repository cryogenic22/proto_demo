import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number; // 0-100
  className?: string;
  variant?: "brand" | "success" | "warning" | "danger";
}

const barColors = {
  brand: "bg-brand-primary",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
};

export function Progress({ value, className, variant = "brand" }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className={cn("w-full bg-neutral-100 rounded-full h-2 overflow-hidden", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500 ease-out", barColors[variant])}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
