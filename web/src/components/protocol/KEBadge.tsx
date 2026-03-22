import { cn } from "@/lib/utils";

interface KEBadgeProps {
  status: string;
  className?: string;
}

const statusConfig: Record<string, { bg: string; text: string; icon: React.ReactNode | null }> = {
  DRAFT: {
    bg: "bg-neutral-100",
    text: "text-neutral-600",
    icon: null,
  },
  VERIFIED: {
    bg: "bg-sky-100",
    text: "text-sky-700",
    icon: (
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  LOCKED: {
    bg: "bg-emerald-100",
    text: "text-emerald-700",
    icon: (
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
  },
};

export function KEBadge({ status, className }: KEBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.DRAFT;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium",
        config.bg,
        config.text,
        className
      )}
    >
      {config.icon}
      {status}
    </span>
  );
}
