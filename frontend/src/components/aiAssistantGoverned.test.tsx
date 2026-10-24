// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() }, API_BASE_URL: '/api/v1' }));
vi.mock('@/services/ai.service', () => ({
  AiRequestError: class extends Error {},
  deleteConversation: vi.fn(), getConversation: vi.fn(), listConversations: vi.fn().mockResolvedValue([]), sendAiMessage: vi.fn(), sendFeedback: vi.fn(),
  streamAiMessage: vi.fn(),
}));

import api from '@/services/api';
import { streamAiMessage } from '@/services/ai.service';
import AiAssistant from './AiAssistant';

const stream = streamAiMessage as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { ai_provider: true } });
  Element.prototype.scrollTo = vi.fn();
});

const ask = async (text: string) => {
  render(<AiAssistant mode="admin" />);
  fireEvent.click(screen.getByLabelText('Open AI Assistant'));
  fireEvent.change(screen.getByPlaceholderText('Ask anything...'), { target: { value: text } });
  fireEvent.click(screen.getByLabelText('Send'));
};

describe('Governed answers in the chat', () => {
  it('names the school documents an answer used', async () => {
    stream.mockImplementation(async (_m: string, _c: unknown, on: (e: unknown) => void) => {
      on({ type: 'done', reply: 'Students arriving after 8:15 are marked late.', offline: false, conversation_id: 'c1', message_id: 'm1', sources: [{ id: 'd1', title: 'Late policy' }], requests: [] });
    });
    await ask('when is a student late?');
    expect(await screen.findByTestId('ai-sources')).toBeTruthy();
    expect(screen.getByTestId('ai-sources').textContent).toBe('Sources: Late policy');
    expect(screen.queryByTestId('ai-requests')).toBeNull();
  });

  it('says plainly that a request is waiting for approval and nothing has been done', async () => {
    stream.mockImplementation(async (_m: string, _c: unknown, on: (e: unknown) => void) => {
      on({ type: 'done', reply: 'I have sent that for approval.', offline: false, conversation_id: 'c1', message_id: 'm2', sources: [],
        requests: [{ id: 'r1', summary: 'Send a fee reminder for invoice INV-7 (Amy Alder) to the family', status: 'pending' }] });
    });
    await ask('remind the family about INV-7');
    await waitFor(() => expect(screen.getByTestId('ai-requests')).toBeTruthy());
    expect(screen.getByTestId('ai-requests').textContent).toMatch(/Waiting for approval, nothing has been done yet/);
    expect(screen.getByTestId('ai-requests').textContent).toMatch(/invoice INV-7/);
    expect(screen.queryByTestId('ai-sources')).toBeNull();
  });
});
