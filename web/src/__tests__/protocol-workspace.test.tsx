import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup, act } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  useParams: () => ({ protocolId: 'pfizer_bnt162' }),
  usePathname: () => '/protocols/pfizer_bnt162',
}));

const mockProtocol = {
  protocol_id: 'pfizer_bnt162',
  document_name: 'test.pdf',
  document_hash: 'abc',
  total_pages: 100,
  metadata: {
    title: 'Test Protocol',
    short_title: 'TP',
    protocol_number: 'P001',
    sponsor: 'Test',
    phase: 'Phase 1',
    therapeutic_area: '',
    indication: '',
    study_type: '',
    arms: [],
    amendment_number: '',
    version: '',
    nct_number: '',
  },
  sections: [
    {
      number: '1',
      title: 'Introduction',
      page: 1,
      end_page: 5,
      level: 1,
      ke_type: 'SECTION',
      content_html: '<p>Intro</p>',
      children: [],
      quality_score: 0.95,
    },
  ],
  tables: [
    {
      table_id: 't1',
      table_type: 'SOA',
      title: 'SoA',
      source_pages: [10],
      schema_info: {
        table_id: 't1',
        column_headers: [],
        row_groups: [],
        merged_regions: [],
        footnote_markers: [],
        num_rows: 2,
        num_cols: 3,
      },
      cells: [
        {
          row: 0,
          col: 0,
          raw_value: 'X',
          normalized_value: null,
          data_type: 'MARKER',
          footnote_markers: [],
          resolved_footnotes: [],
          confidence: 0.98,
          row_header: 'CBC',
          col_header: 'Visit 1',
        },
      ],
      footnotes: [],
      procedures: [],
      visit_windows: [],
      overall_confidence: 0.95,
      flagged_cells: [],
      review_items: [],
      extraction_metadata: {
        passes_run: 2,
        challenger_issues_found: 0,
        reconciliation_conflicts: 0,
        processing_time_seconds: 5,
        timestamp: '',
        model_used: '',
      },
    },
  ],
  procedures: [],
  budget_lines: [],
  quality_summary: {},
  knowledge_elements: [],
  created_at: '2024-01-01',
  pipeline_version: '0.1.0',
};

const mockGetProtocol = vi.fn();
const mockGetKnowledgeElements = vi.fn();
const mockCheckHealth = vi.fn();
const mockAskProtocol = vi.fn();

vi.mock('@/lib/api', () => ({
  getProtocol: (...args: unknown[]) => mockGetProtocol(...args),
  getKnowledgeElements: (...args: unknown[]) => mockGetKnowledgeElements(...args),
  checkHealth: (...args: unknown[]) => mockCheckHealth(...args),
  askProtocol: (...args: unknown[]) => mockAskProtocol(...args),
}));

describe('ProtocolWorkspacePage', () => {
  beforeEach(() => {
    mockGetProtocol.mockReset();
    mockGetKnowledgeElements.mockReset();
    mockCheckHealth.mockReset();
    mockAskProtocol.mockReset();

    mockGetProtocol.mockResolvedValue(mockProtocol);
    mockGetKnowledgeElements.mockResolvedValue([]);
    mockCheckHealth.mockResolvedValue(true);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the workspace with section tree', async () => {
    const { default: Page } = await import(
      '@/app/protocols/[protocolId]/page'
    );

    await act(async () => {
      render(<Page />);
      await new Promise((r) => setTimeout(r, 0));
    });

    // "Introduction" appears both in SectionTree and SectionContent
    expect(mockGetProtocol).toHaveBeenCalledWith('pfizer_bnt162');
    const introElements = screen.getAllByText('Introduction');
    expect(introElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the tables tab', async () => {
    const { default: Page } = await import(
      '@/app/protocols/[protocolId]/page'
    );

    await act(async () => {
      render(<Page />);
      await new Promise((r) => setTimeout(r, 0));
    });

    // "Tables" appears in both the tab bar and Quick Stats sidebar
    const tablesElements = screen.getAllByText('Tables');
    expect(tablesElements.length).toBeGreaterThanOrEqual(1);
  });

  it('wires AssistantPanel (closed panel visible)', async () => {
    const { default: Page } = await import(
      '@/app/protocols/[protocolId]/page'
    );

    await act(async () => {
      render(<Page />);
      await new Promise((r) => setTimeout(r, 0));
    });

    // AssistantPanel renders with translate-x-full when closed
    const panel = document.querySelector('.translate-x-full');
    expect(panel).toBeInTheDocument();
  });

  it('renders Ask button in section content', async () => {
    const { default: Page } = await import(
      '@/app/protocols/[protocolId]/page'
    );

    await act(async () => {
      render(<Page />);
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(screen.getByText('Ask about this section')).toBeInTheDocument();
  });
});
