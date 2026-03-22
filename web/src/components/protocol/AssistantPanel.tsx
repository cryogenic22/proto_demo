"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { CellEvidence } from "./CellEvidence";
import type {
  VerificationStep,
  ChallengeIssue,
  AssistantMessage,
} from "@/lib/api";

// ─── Types ──────────────────────────────────────────────────────────────────

interface CellDataForReview {
  row: number;
  col: number;
  raw_value: string;
  data_type: string;
  confidence: number;
  row_header: string;
  col_header: string;
  footnote_markers: string[];
  resolved_footnotes: string[];
}

export type AssistantMode =
  | { kind: "ask"; sectionNumber: string; sectionTitle: string; sectionContent: string }
  | {
      kind: "review";
      cell: CellDataForReview;
      verifications: VerificationStep[];
      challenges: ChallengeIssue[];
      /** Index within the set of all flagged cells being reviewed */
      currentIndex: number;
      totalFlagged: number;
    }
  | { kind: "closed" };

export interface AssistantPanelProps {
  mode: AssistantMode;
  protocolId: string;
  onClose: () => void;
  onAcceptCell?: (row: number, col: number) => void;
  onCorrectCell?: (row: number, col: number, value: string) => void;
  onFlagCell?: (row: number, col: number, reason: string) => void;
  onNextFlagged?: () => void;
  onSkipFlagged?: () => void;
}

// ─── Component ──────────────────────────────────────────────────────────────

export function AssistantPanel({
  mode,
  protocolId,
  onClose,
  onAcceptCell,
  onCorrectCell,
  onFlagCell,
  onNextFlagged,
  onSkipFlagged,
}: AssistantPanelProps) {
  const isOpen = mode.kind !== "closed";

  return (
    <div
      className={cn(
        "fixed top-14 right-0 bottom-0 w-[380px] bg-white border-l border-neutral-200 shadow-lg z-50",
        "transition-transform duration-200 ease-out flex flex-col",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {mode.kind === "ask" && (
        <AskMode
          sectionNumber={mode.sectionNumber}
          sectionTitle={mode.sectionTitle}
          sectionContent={mode.sectionContent}
          protocolId={protocolId}
          onClose={onClose}
        />
      )}

      {mode.kind === "review" && (
        <ReviewMode
          cell={mode.cell}
          verifications={mode.verifications}
          challenges={mode.challenges}
          currentIndex={mode.currentIndex}
          totalFlagged={mode.totalFlagged}
          onClose={onClose}
          onAccept={() => onAcceptCell?.(mode.cell.row, mode.cell.col)}
          onCorrect={(val) => onCorrectCell?.(mode.cell.row, mode.cell.col, val)}
          onFlag={(reason) => onFlagCell?.(mode.cell.row, mode.cell.col, reason)}
          onNext={onNextFlagged}
          onSkip={onSkipFlagged}
        />
      )}
    </div>
  );
}

// ─── Ask Mode ───────────────────────────────────────────────────────────────

function AskMode({
  sectionNumber,
  sectionTitle,
  sectionContent,
  protocolId,
  onClose,
}: {
  sectionNumber: string;
  sectionTitle: string;
  sectionContent: string;
  protocolId: string;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    const userMsg: AssistantMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // In production this would call askProtocol(protocolId, question, sectionContent)
      // For now, simulate a response
      const assistantMsg: AssistantMessage = {
        role: "assistant",
        content: `Based on **${sectionTitle}**, this section describes the relevant criteria and procedures. The protocol specifies detailed requirements that should be cross-referenced with the Schedule of Activities table for completeness.\n\nPlease note that specific clinical interpretation should be verified with the medical team.`,
        sources: [{ section: sectionNumber, page: 87 }],
      };
      // Simulate delay
      await new Promise((resolve) => setTimeout(resolve, 600));
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't process that question. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, protocolId, sectionContent, sectionNumber, sectionTitle]);

  return (
    <>
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between shrink-0">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-brand-primary font-semibold">Ask about</div>
          <div className="text-sm font-medium text-neutral-800 truncate">
            Section {sectionNumber} {sectionTitle}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600 transition-colors shrink-0"
        >
          <CloseIcon />
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-10 h-10 rounded-full bg-brand-primary-light flex items-center justify-center mx-auto mb-3">
              <ChatBubbleIcon />
            </div>
            <p className="text-sm text-neutral-500">Ask a question about this section...</p>
            <p className="text-[11px] text-neutral-400 mt-1">
              I can help you understand requirements, criteria, and procedures.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {loading && (
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-neutral-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 bg-neutral-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 bg-neutral-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-neutral-200 shrink-0">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={cn(
              "p-2 rounded-lg transition-colors",
              input.trim() && !loading
                ? "bg-brand-primary text-white hover:bg-brand-primary/90"
                : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
            )}
          >
            <SendIcon />
          </button>
        </div>
      </div>
    </>
  );
}

function MessageBubble({ message }: { message: AssistantMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] px-3 py-2 rounded-xl text-[13px] leading-relaxed",
          isUser
            ? "bg-brand-primary text-white rounded-br-sm"
            : "bg-neutral-100 text-neutral-700 rounded-bl-sm"
        )}
      >
        {/* Simple markdown bold support */}
        <div
          dangerouslySetInnerHTML={{
            __html: message.content.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>"),
          }}
        />
        {/* Source citations */}
        {message.sources && message.sources.length > 0 && (
          <div className={cn("mt-1.5 pt-1.5 border-t text-[10px]", isUser ? "border-white/20 text-white/70" : "border-neutral-200 text-neutral-400")}>
            {message.sources.map((src, i) => (
              <span key={i}>
                Source: {src.section}, Page {src.page}
                {i < (message.sources?.length ?? 0) - 1 && " · "}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Review Mode ────────────────────────────────────────────────────────────

function ReviewMode({
  cell,
  verifications,
  challenges,
  currentIndex,
  totalFlagged,
  onClose,
  onAccept,
  onCorrect,
  onFlag,
  onNext,
  onSkip,
}: {
  cell: CellDataForReview;
  verifications: VerificationStep[];
  challenges: ChallengeIssue[];
  currentIndex: number;
  totalFlagged: number;
  onClose: () => void;
  onAccept: () => void;
  onCorrect: (value: string) => void;
  onFlag: (reason: string) => void;
  onNext?: () => void;
  onSkip?: () => void;
}) {
  return (
    <>
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-warning font-semibold">Cell Review</div>
            <div className="text-xs text-neutral-500">
              Reviewing <span className="font-semibold text-neutral-700">{currentIndex + 1}</span>
              {" of "}
              <span className="font-semibold text-neutral-700">{totalFlagged}</span>
              {" flagged cells"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onSkip && (
            <button
              onClick={onSkip}
              className="px-2 py-1 text-[11px] font-medium text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100 rounded-md transition-colors"
            >
              Skip
            </button>
          )}
          {onNext && (
            <button
              onClick={onNext}
              className="px-2 py-1 text-[11px] font-medium text-brand-primary hover:bg-brand-primary-light rounded-md transition-colors flex items-center gap-1"
            >
              Next
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4.5 2.5L8 6L4.5 9.5" />
              </svg>
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600 transition-colors ml-1"
          >
            <CloseIcon />
          </button>
        </div>
      </div>

      {/* Review progress bar */}
      <div className="h-1 bg-neutral-100 shrink-0">
        <div
          className="h-full bg-brand-primary transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / totalFlagged) * 100}%` }}
        />
      </div>

      {/* Cell evidence body */}
      <div className="flex-1 overflow-hidden">
        <CellEvidence
          cell={cell}
          verifications={verifications}
          challengeIssues={challenges}
          onAccept={onAccept}
          onCorrect={onCorrect}
          onFlag={onFlag}
        />
      </div>
    </>
  );
}

// ─── Icons ──────────────────────────────────────────────────────────────────

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M4 4L12 12M12 4L4 12" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2L7 9" />
      <path d="M14 2L9.5 14L7 9L2 6.5L14 2Z" />
    </svg>
  );
}

function ChatBubbleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="#0093D0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 16V13H3C2.44772 13 2 12.5523 2 12V4C2 3.44772 2.44772 3 3 3H17C17.5523 3 18 3.44772 18 4V12C18 12.5523 17.5523 13 17 13H8L4 16Z" />
      <path d="M6 7H14" />
      <path d="M6 10H11" />
    </svg>
  );
}
