"use client";

import { useState, useRef, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Category = "bug" | "issue" | "enhancement" | "feature";
type Priority = "low" | "medium" | "high" | "critical";
type Step = "closed" | "category" | "describe" | "priority" | "confirm" | "submitted";

const CATEGORIES: { key: Category; icon: string; label: string }[] = [
  { key: "bug", icon: "\uD83D\uDC1B", label: "Bug Report" },
  { key: "issue", icon: "\u26A0\uFE0F", label: "Issue" },
  { key: "enhancement", icon: "\u2728", label: "Enhancement" },
  { key: "feature", icon: "\uD83D\uDE80", label: "New Feature" },
];

const PRIORITIES: { key: Priority; label: string; color: string }[] = [
  { key: "low", label: "Low", color: "bg-slate-100 text-slate-700 border-slate-200" },
  { key: "medium", label: "Medium", color: "bg-blue-50 text-blue-700 border-blue-200" },
  { key: "high", label: "High", color: "bg-amber-50 text-amber-700 border-amber-200" },
  { key: "critical", label: "Critical", color: "bg-red-50 text-red-700 border-red-200" },
];

export function FeedbackWidget() {
  const [step, setStep] = useState<Step>("closed");
  const [category, setCategory] = useState<Category | null>(null);
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [submitting, setSubmitting] = useState(false);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus textarea when describe step opens
  useEffect(() => {
    if (step === "describe" && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [step]);

  // Close on Escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && step !== "closed") {
        setStep("closed");
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [step]);

  const extractTitle = (text: string): string => {
    const firstSentence = text.split(/[.\n]/)[0]?.trim() || text.trim();
    return firstSentence.slice(0, 120);
  };

  const handleSubmit = async () => {
    if (!category || !description.trim()) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category,
          title: extractTitle(description),
          description: description.trim(),
          priority,
          page_url: window.location.pathname,
          attachments: [],
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Submission failed" }));
        throw new Error(err.detail || "Failed to submit feedback");
      }

      const data = await res.json();
      setTicketId(data.id);
      setStep("submitted");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setCategory(null);
    setDescription("");
    setPriority("medium");
    setTicketId(null);
    setError(null);
    setStep("closed");
  };

  if (step === "closed") {
    return (
      <button
        onClick={() => setStep("category")}
        className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-brand-primary hover:bg-brand-french text-white shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center group"
        title="Send Feedback"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
      </button>
    );
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
        onClick={() => step !== "submitted" && setStep("closed")}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed right-0 top-0 h-full w-[420px] max-w-full bg-white shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-200">
          <h2 className="text-sm font-semibold text-neutral-800">
            {step === "submitted" ? "Feedback Submitted" : "Send Feedback"}
          </h2>
          <button
            onClick={reset}
            className="p-1 rounded-md hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {/* Step 1: Category */}
          {step === "category" && (
            <div className="space-y-3">
              <p className="text-sm text-neutral-600">What type of feedback do you have?</p>
              <div className="grid grid-cols-2 gap-2">
                {CATEGORIES.map((c) => (
                  <button
                    key={c.key}
                    onClick={() => {
                      setCategory(c.key);
                      setStep("describe");
                    }}
                    className="flex items-center gap-2 px-4 py-3 rounded-lg border border-neutral-200 hover:border-brand-primary hover:bg-brand-primary/5 transition-all text-sm text-neutral-700"
                  >
                    <span className="text-lg">{c.icon}</span>
                    <span>{c.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Description */}
          {step === "describe" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-lg">{CATEGORIES.find((c) => c.key === category)?.icon}</span>
                <span className="text-sm font-medium text-neutral-700">
                  {CATEGORIES.find((c) => c.key === category)?.label}
                </span>
                <button
                  onClick={() => setStep("category")}
                  className="ml-auto text-xs text-brand-primary hover:underline"
                >
                  Change
                </button>
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                  Describe the issue or suggestion
                </label>
                <textarea
                  ref={textareaRef}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Tell us what happened, what you expected, or what you'd like to see..."
                  rows={6}
                  className="w-full px-3 py-2.5 rounded-lg border border-neutral-300 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary text-sm resize-none placeholder:text-neutral-400"
                />
                <div className="text-xs text-neutral-400 mt-1">
                  {description.length > 0 && `Title: "${extractTitle(description)}"`}
                </div>
              </div>
              <button
                onClick={() => description.trim().length >= 3 && setStep("priority")}
                disabled={description.trim().length < 3}
                className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Continue
              </button>
            </div>
          )}

          {/* Step 3: Priority */}
          {step === "priority" && (
            <div className="space-y-4">
              <p className="text-sm text-neutral-600">How urgent is this?</p>
              <div className="space-y-2">
                {PRIORITIES.map((p) => (
                  <button
                    key={p.key}
                    onClick={() => {
                      setPriority(p.key);
                      setStep("confirm");
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-all text-sm ${
                      priority === p.key
                        ? p.color + " border-2"
                        : "border-neutral-200 hover:border-neutral-300"
                    }`}
                  >
                    <span className="font-medium">{p.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 4: Confirm */}
          {step === "confirm" && (
            <div className="space-y-4">
              <p className="text-sm font-medium text-neutral-700">Review before submitting</p>

              <div className="rounded-lg border border-neutral-200 divide-y divide-neutral-100">
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs text-neutral-500">Category</span>
                  <span className="text-sm font-medium capitalize">{category}</span>
                </div>
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs text-neutral-500">Priority</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    PRIORITIES.find((p) => p.key === priority)?.color
                  }`}>{priority}</span>
                </div>
                <div className="px-4 py-2.5">
                  <span className="text-xs text-neutral-500">Title</span>
                  <p className="text-sm text-neutral-800 mt-0.5">{extractTitle(description)}</p>
                </div>
                <div className="px-4 py-2.5">
                  <span className="text-xs text-neutral-500">Description</span>
                  <p className="text-sm text-neutral-600 mt-0.5 line-clamp-4">{description}</p>
                </div>
                <div className="px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs text-neutral-500">Page</span>
                  <span className="text-xs text-neutral-600 font-mono">{typeof window !== "undefined" ? window.location.pathname : ""}</span>
                </div>
              </div>

              {error && (
                <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2.5 text-sm text-red-700">
                  {error}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={reset}
                  className="flex-1 py-2.5 rounded-lg border border-neutral-300 text-sm text-neutral-600 hover:bg-neutral-50 transition-colors"
                >
                  Start Over
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="flex-1 py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
                >
                  {submitting && (
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  )}
                  {submitting ? "Submitting..." : "Submit Feedback"}
                </button>
              </div>
            </div>
          )}

          {/* Step 5: Submitted */}
          {step === "submitted" && ticketId && (
            <div className="text-center space-y-4 pt-8">
              <div className="w-16 h-16 mx-auto rounded-full bg-green-50 flex items-center justify-center">
                <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-neutral-800">Thank you!</p>
                <p className="text-sm text-neutral-500 mt-1">
                  Your feedback has been submitted and is being auto-triaged.
                </p>
              </div>
              <div className="bg-neutral-50 rounded-lg px-4 py-3">
                <p className="text-xs text-neutral-500">Ticket ID</p>
                <p className="text-sm font-mono font-semibold text-brand-primary mt-0.5">{ticketId}</p>
              </div>
              <p className="text-xs text-neutral-400">
                Track progress on the <a href="/feedback" className="text-brand-primary hover:underline">Feedback Tracker</a> page.
              </p>
              <button
                onClick={reset}
                className="mt-4 px-6 py-2 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french transition-colors"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
