"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listProtocols, type ProtocolSummary } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { phaseVariant, formatDate } from "@/lib/utils";

export default function ProtocolLibraryPage() {
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProtocols()
      .then(setProtocols)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <TopBar title="Protocol Library" subtitle="Browse and explore digitized clinical trial protocols" />

      <div className="p-6">
        {/* Hero section */}
        <div className="mb-8">
          <h2 className="text-xl font-bold text-neutral-800">Protocol Library</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Browse and explore digitized clinical trial protocols
          </p>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardBody className="p-5">
                  <div className="animate-pulse space-y-3">
                    <div className="h-4 bg-neutral-200 rounded w-3/4" />
                    <div className="h-3 bg-neutral-100 rounded w-1/2" />
                    <div className="h-3 bg-neutral-100 rounded w-2/3" />
                    <div className="flex gap-2 mt-4">
                      <div className="h-5 bg-neutral-100 rounded w-16" />
                      <div className="h-5 bg-neutral-100 rounded w-12" />
                    </div>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <Card>
            <CardBody className="p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-neutral-700">Failed to load protocols</p>
              <p className="text-xs text-neutral-400 mt-1">{error}</p>
            </CardBody>
          </Card>
        )}

        {/* Empty state */}
        {!loading && !error && protocols.length === 0 && (
          <Card>
            <CardBody className="p-12 text-center">
              <div className="w-16 h-16 rounded-full bg-sky-50 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-brand-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-neutral-800">No protocols yet</h3>
              <p className="text-sm text-neutral-400 mt-1 mb-6 max-w-sm mx-auto">
                Upload a clinical trial protocol to get started with extraction and analysis.
              </p>
              <Link
                href="/"
                className="inline-flex items-center gap-2 px-4 py-2 bg-brand-primary text-white text-sm font-medium rounded-lg hover:bg-brand-french transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                Upload Protocol
              </Link>
            </CardBody>
          </Card>
        )}

        {/* Protocol grid */}
        {!loading && !error && protocols.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {protocols.map((protocol) => (
              <Link key={protocol.protocol_id} href={`/protocols/${protocol.protocol_id}`}>
                <Card className="hover:shadow-md hover:border-brand-primary/30 transition-all duration-200 cursor-pointer h-full">
                  <CardBody className="p-5">
                    {/* Title and phase */}
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <h3 className="text-sm font-semibold text-neutral-800 leading-snug line-clamp-2">
                        {protocol.metadata.title || protocol.document_name}
                      </h3>
                      {protocol.metadata.phase && (
                        <Badge variant={phaseVariant(protocol.metadata.phase)} className="shrink-0">
                          {protocol.metadata.phase}
                        </Badge>
                      )}
                    </div>

                    {/* Metadata */}
                    <div className="space-y-1.5 mb-4">
                      {protocol.metadata.sponsor && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-neutral-400 w-20 shrink-0">Sponsor</span>
                          <span className="text-neutral-700 font-medium">{protocol.metadata.sponsor}</span>
                        </div>
                      )}
                      {protocol.metadata.therapeutic_area && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-neutral-400 w-20 shrink-0">Area</span>
                          <span className="text-neutral-600">{protocol.metadata.therapeutic_area}</span>
                        </div>
                      )}
                      {protocol.metadata.indication && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-neutral-400 w-20 shrink-0">Indication</span>
                          <span className="text-neutral-600 truncate">{protocol.metadata.indication}</span>
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between pt-3 border-t border-neutral-100">
                      <div className="flex items-center gap-3 text-[11px] text-neutral-400">
                        <span>{protocol.total_pages} pages</span>
                        {protocol.metadata.protocol_number && (
                          <span className="font-mono">{protocol.metadata.protocol_number}</span>
                        )}
                      </div>
                      <span className="text-[11px] text-neutral-400">
                        {formatDate(protocol.created_at)}
                      </span>
                    </div>
                  </CardBody>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
