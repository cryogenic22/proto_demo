import type { SectionNode } from "@/lib/api";

interface SectionContentProps {
  section: SectionNode | null;
}

export function SectionContent({ section }: SectionContentProps) {
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
      </div>

      {/* HTML content */}
      {section.content_html ? (
        <div
          className="section-content prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: section.content_html }}
        />
      ) : (
        <p className="text-sm text-neutral-400 italic">No content available for this section.</p>
      )}
    </div>
  );
}
