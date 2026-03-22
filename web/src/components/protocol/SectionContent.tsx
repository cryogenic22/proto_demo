import type { SectionNode } from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";

interface SectionContentProps {
  section: SectionNode | null;
  onAsk?: (section: SectionNode) => void;
}

export function SectionContent({ section, onAsk }: SectionContentProps) {
  if (!section) {
    return (
      <div className="flex items-center justify-center h-64 text-neutral-400 text-sm">
        <div className="text-center">
          <svg className="w-10 h-10 mx-auto mb-3 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <p>Select a section to view its content</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Section heading */}
      <div className="mb-6 pb-4 border-b border-neutral-100">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-xs text-neutral-400">{section.number}</span>
          {section.quality_score !== null && (
            <span className="text-[10px] text-neutral-500 bg-neutral-100 px-1.5 py-0.5 rounded-full">
              Quality: {(section.quality_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <h2 className="text-lg font-semibold text-neutral-800">{section.title}</h2>
        <p className="text-xs text-neutral-400 mt-1">
          Page {section.page}
          {section.end_page && section.end_page !== section.page ? ` – ${section.end_page}` : ""}
          {section.ke_type && ` · ${section.ke_type}`}
        </p>
        {onAsk && (
          <button
            onClick={() => onAsk(section)}
            className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-primary bg-brand-primary-light rounded-lg hover:bg-brand-primary/10 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
            </svg>
            Ask about this section
          </button>
        )}
      </div>

      {/* HTML content */}
      {section.content_html ? (
        <div
          className="section-content max-w-none"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(section.content_html) }}
        />
      ) : (
        <p className="text-sm text-neutral-400 italic">No content available for this section.</p>
      )}
    </div>
  );
}
