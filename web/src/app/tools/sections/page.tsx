"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listProtocols,
  getProtocol,
  parseSections,
  type ProtocolSummary,
  type ProtocolFull,
  type SectionNode,
  type ParsedSection,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

type SectionItem = {
  number: string;
  title: string;
  page: number;
  end_page: number | null;
  level: number;
  content_html?: string;
  quality_score?: number | null;
  children: SectionItem[];
};

function toSectionItems(sections: SectionNode[] | ParsedSection[]): SectionItem[] {
  return sections.map((s) => ({
    number: s.number,
    title: s.title,
    page: s.page,
    end_page: s.end_page,
    level: s.level,
    content_html: (s as SectionNode).content_html || undefined,
    quality_score: (s as SectionNode).quality_score ?? null,
    children: toSectionItems(s.children || []),
  }));
}

function countAll(sections: SectionItem[]): number {
  return sections.reduce((sum, s) => sum + 1 + countAll(s.children), 0);
}

export default function SectionExplorerPage() {
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [sections, setSections] = useState<SectionItem[]>([]);
  const [selectedSection, setSelectedSection] = useState<SectionItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<string>("");

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);

  // Load protocol list
  useEffect(() => {
    listProtocols().then(setProtocols).catch(() => {});
  }, []);

  // Load sections from stored protocol
  const loadFromProtocol = useCallback(async (protocolId: string) => {
    setLoading(true);
    setError(null);
    setSelectedSection(null);
    setMethod("");
    try {
      const proto = await getProtocol(protocolId);
      const items = toSectionItems(proto.sections);
      setSections(items);
      setMethod("stored");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setSections([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Parse sections from uploaded file
  const handleUploadParse = useCallback(async () => {
    if (!uploadFile) return;
    setParsing(true);
    setError(null);
    setSelectedSection(null);
    setSelectedId("");
    try {
      const result = await parseSections(uploadFile);
      const items = toSectionItems(result.sections);
      setSections(items);
      setMethod(result.method);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Parse failed");
      setSections([]);
    } finally {
      setParsing(false);
    }
  }, [uploadFile]);

  const handleProtocolSelect = (id: string) => {
    setSelectedId(id);
    if (id) loadFromProtocol(id);
    else setSections([]);
  };

  const totalSections = countAll(sections);

  return (
    <div>
      <TopBar title="Section Explorer" subtitle="Parse and browse protocol document structure" />

      <div className="p-6 space-y-4">
        {/* Source selector */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-end gap-4 flex-wrap">
              {/* From stored protocol */}
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-neutral-600 block mb-1">
                  Load from stored protocol
                </label>
                <select
                  value={selectedId}
                  onChange={(e) => handleProtocolSelect(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                >
                  <option value="">Select a protocol...</option>
                  {protocols.map((p) => (
                    <option key={p.protocol_id} value={p.protocol_id}>
                      {p.metadata.short_title || p.metadata.title || p.document_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="text-xs text-neutral-400 font-medium py-2">OR</div>

              {/* Upload new */}
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-neutral-600 block mb-1">
                  Upload PDF to parse
                </label>
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-sm text-neutral-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-brand-primary file:text-white file:cursor-pointer hover:file:bg-brand-french"
                />
              </div>
              <button
                onClick={handleUploadParse}
                disabled={!uploadFile || parsing}
                className={cn(
                  "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                  uploadFile && !parsing
                    ? "bg-brand-primary text-white hover:bg-brand-french"
                    : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                )}
              >
                {parsing ? "Parsing..." : "Parse Sections"}
              </button>
            </div>
          </CardBody>
        </Card>

        {/* Error */}
        {error && (
          <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* Loading */}
        {(loading || parsing) && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-neutral-400">{parsing ? "Parsing document sections..." : "Loading sections..."}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {!loading && !parsing && sections.length > 0 && (
          <div className="flex gap-4" style={{ height: "calc(100vh - 280px)" }}>
            {/* Left: Section tree */}
            <Card className="w-[360px] shrink-0 flex flex-col overflow-hidden">
              <CardHeader className="shrink-0">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
                    Document Outline
                  </h3>
                  <div className="flex items-center gap-2">
                    <Badge variant="brand">{totalSections} sections</Badge>
                    {method && <Badge variant="neutral">{method}</Badge>}
                  </div>
                </div>
              </CardHeader>
              <div className="flex-1 overflow-y-auto">
                {sections.map((s) => (
                  <TreeNode
                    key={s.number || s.title}
                    section={s}
                    selected={selectedSection}
                    onSelect={setSelectedSection}
                    depth={0}
                  />
                ))}
              </div>
            </Card>

            {/* Right: Section content */}
            <Card className="flex-1 flex flex-col overflow-hidden">
              {selectedSection ? (
                <>
                  <CardHeader className="shrink-0">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded">
                        {selectedSection.number}
                      </span>
                      <h3 className="text-sm font-semibold text-neutral-800">
                        {selectedSection.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-neutral-400">
                      <span>Page {selectedSection.page}{selectedSection.end_page && selectedSection.end_page !== selectedSection.page ? ` – ${selectedSection.end_page}` : ""}</span>
                      <span>Level {selectedSection.level}</span>
                      {selectedSection.quality_score != null && (
                        <span>Quality: {(selectedSection.quality_score * 100).toFixed(0)}%</span>
                      )}
                      {selectedSection.children.length > 0 && (
                        <span>{selectedSection.children.length} subsections</span>
                      )}
                    </div>
                  </CardHeader>
                  <div className="flex-1 overflow-y-auto p-6">
                    {selectedSection.content_html ? (
                      <div
                        className="section-content max-w-none"
                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(selectedSection.content_html) }}
                      />
                    ) : (
                      <p className="text-sm text-neutral-400 italic">
                        No content available. Section content is only populated for stored protocols that have been fully extracted.
                      </p>
                    )}
                  </div>
                </>
              ) : (
                <CardBody className="flex items-center justify-center h-full">
                  <div className="text-center text-neutral-400">
                    <svg className="w-10 h-10 mx-auto mb-3 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                    <p className="text-sm">Select a section to view its content</p>
                  </div>
                </CardBody>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

function TreeNode({
  section,
  selected,
  onSelect,
  depth,
}: {
  section: SectionItem;
  selected: SectionItem | null;
  onSelect: (s: SectionItem) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isSelected = selected === section;
  const hasChildren = section.children.length > 0;

  return (
    <div>
      <button
        onClick={() => {
          onSelect(section);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-2 py-2 px-3 text-left transition-colors group hover:bg-neutral-100",
          isSelected && "bg-brand-primary-light"
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {hasChildren ? (
          <svg
            className={cn("w-3 h-3 text-neutral-400 shrink-0 transition-transform", expanded && "rotate-90")}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <span className={cn(
          "font-mono text-[11px] shrink-0",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-400"
        )}>
          {section.number}
        </span>
        <span className={cn(
          "truncate text-xs",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-700"
        )}>
          {section.title}
        </span>
        <span className="ml-auto text-[10px] text-neutral-400 shrink-0 font-mono">
          p.{section.page}
        </span>
      </button>
      {hasChildren && expanded && section.children.map((child) => (
        <TreeNode
          key={child.number || child.title}
          section={child}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}
