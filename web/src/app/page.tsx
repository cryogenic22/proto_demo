"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { UploadZone } from "@/components/extraction/UploadZone";
import { ProcessingStatus } from "@/components/extraction/ProcessingStatus";
import { uploadProtocol } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

export default function HomePage() {
  const router = useRouter();
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "uploading"; file: File }
    | { kind: "processing"; jobId: string; file: File }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  const handleFileSelected = async (file: File) => {
    setState({ kind: "uploading", file });

    try {
      const { job_id } = await uploadProtocol(file);
      setState({ kind: "processing", jobId: job_id, file });
    } catch (err: any) {
      setState({ kind: "error", message: err.message || "Upload failed" });
    }
  };

  return (
    <>
      <TopBar
        title="Upload Protocol"
        subtitle="Extract tables from clinical trial protocol PDFs"
      />

      <main className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Hero section */}
        <div className="text-center py-4">
          <h2 className="text-2xl font-semibold text-neutral-800 mb-2">
            Protocol Table Extraction
          </h2>
          <p className="text-sm text-neutral-500 max-w-lg mx-auto">
            Upload a clinical trial protocol PDF to extract all tables including
            Schedule of Activities, demographics, lab parameters, and more.
            Tables are digitized with footnote resolution, procedure normalization,
            and confidence scoring.
          </p>
        </div>

        {/* Upload or status */}
        {state.kind === "idle" && (
          <UploadZone onFileSelected={handleFileSelected} />
        )}

        {state.kind === "uploading" && (
          <Card className="max-w-2xl mx-auto">
            <CardBody className="flex items-center justify-center py-12 gap-3">
              <div className="w-5 h-5 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-neutral-600">Uploading {state.file.name}...</span>
            </CardBody>
          </Card>
        )}

        {state.kind === "processing" && (
          <ProcessingStatus
            jobId={state.jobId}
            fileName={state.file.name}
            fileSize={state.file.size}
          />
        )}

        {state.kind === "error" && (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="bg-red-50 rounded-xl px-5 py-4 text-sm text-red-700 border border-red-200">
              <p className="font-medium mb-1">Upload failed</p>
              <p className="text-xs">{state.message}</p>
            </div>
            <button
              onClick={() => setState({ kind: "idle" })}
              className="text-sm text-brand-primary hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Pipeline info */}
        {state.kind === "idle" && (
          <div className="grid grid-cols-3 gap-4 pt-4">
            {[
              {
                title: "Multi-Pass Extraction",
                desc: "Two independent extraction passes with consistency checking reduce hallucinations",
                icon: (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
                  </svg>
                ),
              },
              {
                title: "Footnote Resolution",
                desc: "Superscript markers are matched to definitions and anchored to specific cells",
                icon: (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                  </svg>
                ),
              },
              {
                title: "Adversarial Validation",
                desc: "A challenger agent cross-checks extractions against source images to catch errors",
                icon: (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                  </svg>
                ),
              },
            ].map((feature) => (
              <Card key={feature.title}>
                <CardBody className="space-y-2">
                  <div className="w-9 h-9 rounded-lg bg-sky-50 flex items-center justify-center text-brand-primary">
                    {feature.icon}
                  </div>
                  <h3 className="text-sm font-semibold text-neutral-800">{feature.title}</h3>
                  <p className="text-xs text-neutral-500 leading-relaxed">{feature.desc}</p>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
