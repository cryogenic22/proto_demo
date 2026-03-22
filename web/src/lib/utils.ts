export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(1)} ${sizes[i]}`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.95) return "text-success";
  if (confidence >= 0.85) return "text-brand-primary";
  if (confidence >= 0.70) return "text-warning";
  return "text-danger";
}

export function confidenceBg(confidence: number): string {
  if (confidence >= 0.95) return "bg-emerald-50";
  if (confidence >= 0.85) return "bg-sky-50";
  if (confidence >= 0.70) return "bg-amber-50";
  return "bg-red-50";
}

export function costTierLabel(tier: string): string {
  switch (tier) {
    case "LOW": return "$";
    case "MEDIUM": return "$$";
    case "HIGH": return "$$$";
    case "VERY_HIGH": return "$$$$";
    default: return tier;
  }
}

export function costTierColor(tier: string): string {
  switch (tier) {
    case "LOW": return "bg-neutral-100 text-neutral-600";
    case "MEDIUM": return "bg-sky-100 text-sky-700";
    case "HIGH": return "bg-amber-100 text-amber-700";
    case "VERY_HIGH": return "bg-red-100 text-red-700";
    default: return "bg-neutral-100 text-neutral-600";
  }
}

export function phaseVariant(phase: string): "brand" | "success" | "warning" | "danger" | "neutral" | "info" {
  const p = phase.toLowerCase();
  if (p.includes("1")) return "info";
  if (p.includes("2")) return "brand";
  if (p.includes("3")) return "success";
  if (p.includes("4")) return "warning";
  return "neutral";
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

export function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
