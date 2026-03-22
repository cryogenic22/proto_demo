"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getProtocol, type ProtocolFull } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardBody } from "@/components/ui/Card";
import { BudgetTable } from "@/components/protocol/BudgetTable";
import { formatCurrency } from "@/lib/utils";

export default function BudgetPage() {
  const params = useParams();
  const protocolId = params.protocolId as string;

  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProtocol(protocolId)
      .then(setProtocol)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [protocolId]);

  if (loading) {
    return (
      <div>
        <TopBar title="Loading..." subtitle="Fetching budget data" />
        <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
          <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !protocol) {
    return (
      <div>
        <TopBar title="Error" />
        <div className="p-6">
          <Card>
            <CardBody className="p-8 text-center">
              <p className="text-sm font-medium text-neutral-700">Failed to load budget data</p>
              <p className="text-xs text-neutral-400 mt-1">{error}</p>
              <Link
                href={`/protocols/${protocolId}`}
                className="inline-flex items-center gap-1 text-sm text-brand-primary hover:underline mt-4"
              >
                &larr; Back to protocol
              </Link>
            </CardBody>
          </Card>
        </div>
      </div>
    );
  }

  const lines = protocol.budget_lines;
  const totalCost = lines.reduce((sum, l) => sum + l.estimated_unit_cost * l.total_occurrences, 0);
  const cptCoded = lines.filter((l) => l.cpt_code).length;
  const avgConfidence =
    lines.length > 0
      ? lines.reduce((sum, l) => sum + l.avg_confidence, 0) / lines.length
      : 0;

  return (
    <div>
      <TopBar
        title={protocol.metadata.short_title || protocol.document_name}
        subtitle="Site Budget Estimate"
      />

      <div className="p-6 space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <Link href="/protocols" className="hover:text-brand-primary transition-colors">
            Protocols
          </Link>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <Link
            href={`/protocols/${protocolId}`}
            className="hover:text-brand-primary transition-colors"
          >
            {protocol.metadata.short_title || protocol.document_name}
          </Link>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span className="text-neutral-600 font-medium">Budget</span>
        </div>

        {/* Header */}
        <div>
          <h2 className="text-xl font-bold text-neutral-800">Site Budget Estimate</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Estimated per-patient site costs based on extracted procedures and visit schedule
          </p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard
            label="Total Procedures"
            value={String(lines.length)}
            icon={
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
              </svg>
            }
            iconBg="bg-sky-50"
            iconColor="text-sky-600"
          />
          <SummaryCard
            label="Per-Patient Cost"
            value={formatCurrency(totalCost)}
            icon={
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
          />
          <SummaryCard
            label="CPT-Coded"
            value={`${cptCoded} / ${lines.length}`}
            icon={
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
              </svg>
            }
            iconBg="bg-purple-50"
            iconColor="text-purple-600"
          />
          <SummaryCard
            label="Avg. Confidence"
            value={`${(avgConfidence * 100).toFixed(0)}%`}
            icon={
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            }
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
          />
        </div>

        {/* Budget table */}
        <Card>
          <BudgetTable lines={lines} />
        </Card>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon,
  iconBg,
  iconColor,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
}) {
  return (
    <Card>
      <CardBody className="p-4 flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
          <span className={iconColor}>{icon}</span>
        </div>
        <div>
          <p className="text-[11px] text-neutral-400 uppercase tracking-wide font-medium">{label}</p>
          <p className="text-lg font-bold text-neutral-800 font-mono">{value}</p>
        </div>
      </CardBody>
    </Card>
  );
}
