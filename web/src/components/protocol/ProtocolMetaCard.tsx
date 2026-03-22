import type { ProtocolMetadata } from "@/lib/api";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface ProtocolMetaCardProps {
  metadata: ProtocolMetadata;
  className?: string;
}

function phaseVariant(phase: string): "brand" | "success" | "warning" | "danger" | "neutral" | "info" {
  const p = phase.toLowerCase();
  if (p.includes("1")) return "info";
  if (p.includes("2")) return "brand";
  if (p.includes("3")) return "success";
  if (p.includes("4")) return "warning";
  return "neutral";
}

interface FieldRowProps {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}

function FieldRow({ label, value, mono }: FieldRowProps) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-2 py-1.5">
      <dt className="text-[11px] font-medium text-neutral-400 uppercase tracking-wide w-28 shrink-0 pt-0.5">
        {label}
      </dt>
      <dd className={cn("text-xs text-neutral-700", mono && "font-mono")}>{value}</dd>
    </div>
  );
}

export function ProtocolMetaCard({ metadata, className }: ProtocolMetaCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
            Protocol Details
          </h3>
          {metadata.phase && (
            <Badge variant={phaseVariant(metadata.phase)}>{metadata.phase}</Badge>
          )}
        </div>
      </CardHeader>
      <CardBody className="py-2">
        <dl className="divide-y divide-neutral-50">
          <FieldRow label="Sponsor" value={metadata.sponsor} />
          <FieldRow label="Protocol #" value={metadata.protocol_number} mono />
          <FieldRow label="NCT #" value={metadata.nct_number} mono />
          <FieldRow label="Therapeutic" value={metadata.therapeutic_area} />
          <FieldRow label="Indication" value={metadata.indication} />
          <FieldRow label="Study Type" value={metadata.study_type} />
          <FieldRow label="Version" value={metadata.version} />
          <FieldRow label="Amendment" value={metadata.amendment_number} />
          {metadata.arms && metadata.arms.length > 0 && (
            <div className="flex items-start gap-2 py-1.5">
              <dt className="text-[11px] font-medium text-neutral-400 uppercase tracking-wide w-28 shrink-0 pt-0.5">
                Arms
              </dt>
              <dd className="flex flex-wrap gap-1">
                {metadata.arms.map((arm, i) => (
                  <Badge key={i} variant="neutral">{arm}</Badge>
                ))}
              </dd>
            </div>
          )}
        </dl>
      </CardBody>
    </Card>
  );
}
