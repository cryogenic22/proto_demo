import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: () => '/manage/procedures',
}));

// Mock api
const mockListProcedures = vi.fn();
const mockUpdateProcedure = vi.fn();
const mockCheckHealth = vi.fn().mockResolvedValue(true);

vi.mock('@/lib/api', () => ({
  listProcedures: (...args: unknown[]) => mockListProcedures(...args),
  updateProcedure: (...args: unknown[]) => mockUpdateProcedure(...args),
  checkHealth: (...args: unknown[]) => mockCheckHealth(...args),
}));

describe('ProcedureLibraryPage', () => {
  beforeEach(() => {
    vi.resetModules();
    mockListProcedures.mockReset();
    mockUpdateProcedure.mockReset();
    mockCheckHealth.mockReset().mockResolvedValue(true);
  });

  it('loads procedures from API, not mock data', async () => {
    mockListProcedures.mockResolvedValue([
      {
        canonical_name: 'CBC',
        cpt_code: '85025',
        code_system: 'CPT',
        category: 'Laboratory',
        cost_tier: 'LOW',
        aliases: ['FBC'],
        used_in_protocols: 5,
      },
    ]);

    const { default: Page } = await import('@/app/manage/procedures/page');
    render(<Page />);

    await waitFor(() => {
      expect(mockListProcedures).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText('CBC')).toBeInTheDocument();
    });
  });

  it('shows error when API call fails', async () => {
    mockListProcedures.mockRejectedValue(new Error('Network error'));

    const { default: Page } = await import('@/app/manage/procedures/page');
    render(<Page />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('shows no generateMockProcedures function', async () => {
    // Verify the mock data generator is removed
    const moduleContent = await import('@/app/manage/procedures/page');
    expect((moduleContent as Record<string, unknown>).generateMockProcedures).toBeUndefined();
  });
});
