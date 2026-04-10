"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { UploadZone } from "@/components/extraction/UploadZone";
import { ProcessingStatus } from "@/components/extraction/ProcessingStatus";
import { uploadProtocol, getJobStatus, ExtractionMode } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

type PageState =
  | { kind: "idle" }
  | { kind: "uploading"; file: File }
  | { kind: "processing"; jobId: string; fileName: string; fileSize: number }
  | { kind: "error"; message: string };

const EXTRACTION_MODES: {
  value: ExtractionMode;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    value: "full",
    label: "Full Digitization",
    description: "Extract everything — text, tables, formulas, sections, formatting. No SoA-specific processing.",
    icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
  },
  {
    value: "soa",
    label: "SoA Tables",
    description: "Extract Schedule of Activities tables with procedures, visit windows, and footnotes for site budgets.",
    icon: "M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v.75",
  },
  {
    value: "soa_plus",
    label: "SoA + Protocol Elements",
    description: "Full extraction: SoA tables plus eligibility criteria, study design, endpoints, and knowledge elements.",
    icon: "M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [state, setState] = useState<PageState>({ kind: "idle" });
  const [extractionMode, setExtractionMode] = useState<ExtractionMode>("soa");

  // Resume any in-progress job from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("active_job");
    if (!saved) return;
    try {
      const { jobId, fileName, fileSize } = JSON.parse(saved);
      getJobStatus(jobId).then((s) => {
        if (s.status === "processing" || s.status === "pending") {
          setState({ kind: "processing", jobId, fileName, fileSize });
        } else {
          localStorage.removeItem("active_job");
        }
      }).catch(() => localStorage.removeItem("active_job"));
    } catch {
      localStorage.removeItem("active_job");
    }
  }, []);

  const handleFileSelected = async (file: File) => {
    setState({ kind: "uploading", file });

    try {
      const { job_id } = await uploadProtocol(file, extractionMode);
      localStorage.setItem(
        "active_job",
        JSON.stringify({ jobId: job_id, fileName: file.name, fileSize: file.size })
      );
      setState({ kind: "processing", jobId: job_id, fileName: file.name, fileSize: file.size });
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

        {/* Extraction mode selector */}
        {state.kind === "idle" && (
          <div className="max-w-2xl mx-auto">
            <label className="block text-xs font-medium text-neutral-500 mb-2 uppercase tracking-wide">
              Extraction Mode
            </label>
            <div className="grid grid-cols-3 gap-3">
              {EXTRACTION_MODES.map((mode) => (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() => setExtractionMode(mode.value)}
                  className={`relative text-left p-3 rounded-xl border-2 transition-all ${
                    extractionMode === mode.value
                      ? "border-brand-primary bg-sky-50 shadow-sm"
                      : "border-neutral-200 hover:border-neutral-300 bg-white"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      extractionMode === mode.value ? "bg-brand-primary text-white" : "bg-neutral-100 text-neutral-400"
                    }`}>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d={mode.icon} />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <h4 className={`text-sm font-semibold ${
                        extractionMode === mode.value ? "text-brand-primary" : "text-neutral-700"
                      }`}>
                        {mode.label}
                      </h4>
                      <p className="text-[11px] text-neutral-500 leading-snug mt-0.5">{mode.description}</p>
                    </div>
                  </div>
                  {extractionMode === mode.value && (
                    <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-brand-primary flex items-center justify-center">
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

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
            fileName={state.fileName}
            fileSize={state.fileSize}
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
