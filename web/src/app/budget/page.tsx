"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listProtocols, type ProtocolSummary } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

export default function BudgetLandingPage() {
  const router = useRouter();
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listProtocols()
      .then(setProtocols)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopBar title="Site Budget Wizard" subtitle="Select a protocol to calculate per-patient site costs" />
      <div className="p-6 max-w-3xl mx-auto">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="space-y-3">
            {protocols.map((p) => (
              <button
                key={p.protocol_id}
                onClick={() => router.push(`/protocols/${p.protocol_id}/budget-wizard`)}
                className="w-full text-left"
              >
                <Card className="hover:shadow-md hover:border-emerald-300 transition-all cursor-pointer">
                  <CardBody className="p-4 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0">
                      <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-neutral-800 truncate">
                        {p.metadata.short_title || p.metadata.title || p.document_name}
                      </h3>
                      <p className="text-xs text-neutral-400 mt-0.5">
                        {p.metadata.sponsor} · {p.metadata.phase} · {p.total_pages} pages
                      </p>
                    </div>
                    <svg className="w-4 h-4 text-neutral-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </CardBody>
                </Card>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
