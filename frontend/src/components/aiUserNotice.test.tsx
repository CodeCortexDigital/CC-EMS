// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() }, API_BASE_URL: '/api/v1' }));
vi.mock('@/services/ai.service', () => {
  class AiRequestError extends Error {
    constructor(message: string, public status: number, public explained = false, public code = '') { super(message); }
  }
  return {
    AiRequestError,
    deleteConversation: vi.fn(), getConversation: vi.fn(), listConversations: vi.fn().mockResolvedValue([]), sendAiMessage: vi.fn(), sendFeedback: vi.fn(),
    streamAiMessage: vi.fn(), getAiUserNotice: vi.fn(), acceptAiUserNotice: vi.fn(),
  };
});

import api from '@/services/api';
import { acceptAiUserNotice, AiRequestError, getAiUserNotice, streamAiMessage } from '@/services/ai.service';
import AiAssistant from './AiAssistant';

const stream = streamAiMessage as unknown as ReturnType<typeof vi.fn>;
const getNotice = getAiUserNotice as unknown as ReturnType<typeof vi.fn>;
const accept = acceptAiUserNotice as unknown as ReturnType<typeof vi.fn>;
const TEXT = 'What you type is sent to an outside AI provider. The AI can be wrong.';

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { ai_provider: true } });
  Element.prototype.scrollTo = vi.fn();
  getNotice.mockResolvedValue({ version: 1, text: TEXT, accepted: false, required: true });
});

const ask = async (text: string) => {
  render(<AiAssistant mode="teacher" />);
  fireEvent.click(screen.getByLabelText('Open AI Assistant'));
  fireEvent.change(screen.getByPlaceholderText('Ask anything...'), { target: { value: text } });
  fireEvent.click(screen.getByLabelText('Send'));
};

describe('AI use notice before the first question', () => {
  it('shows the notice instead of an answer when the school requires it', async () => {
    stream.mockRejectedValue(new AiRequestError('Please read and accept the AI use notice before using AI.', 403, true, 'ai_notice_required'));
    await ask('how many are absent?');
    expect(await screen.findByRole('alertdialog', { name: 'AI use notice' })).toBeTruthy();
    expect(screen.getByText(TEXT)).toBeTruthy();
    expect(screen.queryByText('how many are absent?')).toBeNull();                      // the question is not shown as sent
  });

  it('accepting records it and then asks the waiting question', async () => {
    stream.mockRejectedValueOnce(new AiRequestError('Please accept.', 403, true, 'ai_notice_required'));
    accept.mockResolvedValue({ version: 1, text: TEXT, accepted: true, required: true });
    await ask('how many are absent?');
    stream.mockImplementationOnce(async (_m: string, _c: unknown, on: (e: unknown) => void) => {
      on({ type: 'done', reply: 'Four.', offline: false, conversation_id: 'c1', message_id: 'm1', sources: [], requests: [] });
    });
    fireEvent.click(await screen.findByRole('button', { name: 'I have read this and accept' }));
    await waitFor(() => expect(accept).toHaveBeenCalled());
    await waitFor(() => expect(stream).toHaveBeenLastCalledWith('how many are absent?', undefined, expect.any(Function), expect.anything()));
    expect(await screen.findByText('Four.')).toBeTruthy();
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  it('"Not now" closes it without accepting', async () => {
    stream.mockRejectedValue(new AiRequestError('Please accept.', 403, true, 'ai_notice_required'));
    await ask('hello');
    fireEvent.click(await screen.findByRole('button', { name: 'Not now' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(accept).not.toHaveBeenCalled();
  });

  it('other refusals are shown as the answer, with their reason', async () => {
    stream.mockRejectedValue(new AiRequestError('AI is paused: this school has no record that the AI provider does not train on what is sent.', 403, true, 'ai_training_required'));
    await ask('hello');
    expect(await screen.findByText(/AI is paused/)).toBeTruthy();
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });
});
