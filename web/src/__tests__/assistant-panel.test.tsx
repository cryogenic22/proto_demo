import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { AssistantPanel } from '@/components/protocol/AssistantPanel';

// Mock the api module
const mockAskProtocol = vi.fn();

vi.mock('@/lib/api', () => ({
  askProtocol: (...args: unknown[]) => mockAskProtocol(...args),
}));

describe('AssistantPanel', () => {
  afterEach(() => {
    cleanup();
    mockAskProtocol.mockReset();
  });

  it('renders closed state with translate-x-full', () => {
    const { container } = render(
      <AssistantPanel mode={{ kind: "closed" }} protocolId="test" onClose={() => {}} />
    );
    expect(container.querySelector('.translate-x-full')).toBeInTheDocument();
  });

  it('renders ask mode with section context', () => {
    render(
      <AssistantPanel
        mode={{ kind: "ask", sectionNumber: "5.1", sectionTitle: "Inclusion Criteria", sectionContent: "<p>test</p>" }}
        protocolId="test"
        onClose={() => {}}
      />
    );
    expect(screen.getByText(/Section 5.1/)).toBeInTheDocument();
    expect(screen.getByText(/Inclusion Criteria/)).toBeInTheDocument();
  });

  it('calls askProtocol when user sends question', async () => {
    mockAskProtocol.mockResolvedValue({
      role: 'assistant',
      content: 'Test answer',
      sources: [],
    });

    render(
      <AssistantPanel
        mode={{ kind: "ask", sectionNumber: "5.1", sectionTitle: "Test", sectionContent: "" }}
        protocolId="test-protocol"
        onClose={() => {}}
      />
    );

    const input = screen.getByPlaceholderText('Ask a question...');
    fireEvent.change(input, { target: { value: 'What are the criteria?' } });

    // Find the send button - it's in the input area, the one that isn't the close button
    const buttons = screen.getAllByRole('button');
    // Send button is the last one (close button is first, in the header)
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(mockAskProtocol).toHaveBeenCalledWith('test-protocol', 'What are the criteria?', '');
    });
  });

  it('displays error message when askProtocol fails', async () => {
    mockAskProtocol.mockRejectedValue(new Error('Network error'));

    render(
      <AssistantPanel
        mode={{ kind: "ask", sectionNumber: "5.1", sectionTitle: "Test", sectionContent: "" }}
        protocolId="test-protocol"
        onClose={() => {}}
      />
    );

    const input = screen.getByPlaceholderText('Ask a question...');
    fireEvent.change(input, { target: { value: 'Test question' } });

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(/couldn't process that question/)).toBeInTheDocument();
    });
  });

  it('displays LLM not configured message on 503 error', async () => {
    mockAskProtocol.mockRejectedValue(new Error('503 Service Unavailable'));

    render(
      <AssistantPanel
        mode={{ kind: "ask", sectionNumber: "5.1", sectionTitle: "Test", sectionContent: "" }}
        protocolId="test-protocol"
        onClose={() => {}}
      />
    );

    const input = screen.getByPlaceholderText('Ask a question...');
    fireEvent.change(input, { target: { value: 'Test question' } });

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(/LLM is not configured/)).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <AssistantPanel
        mode={{ kind: "ask", sectionNumber: "1", sectionTitle: "Intro", sectionContent: "" }}
        protocolId="test"
        onClose={onClose}
      />
    );

    // The close button is the first button in the header area
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
