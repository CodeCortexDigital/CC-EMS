// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : []),
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { toast } from 'sonner';
import api from '@/services/api';
import AiSettingsPage from './AiSettingsPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const put = api.put as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const base = {
  ai_enabled: true,
  approval: { required: 1, approvers: [] as string[], candidates: [{ id: 'u1', name: 'Head Teacher', email: 'head@a.test', role: 'admin' }, { id: 'u2', name: 'Deputy', email: 'deputy@a.test', role: 'admin' }] },
  provider: { configured: false, name: '', note: 'No AI provider is set up on the server, so features use built-in templates and say so.' },
  contact_details_shared: false,
  features: [
    { key: 'ai_translation', label: 'Translation', description: 'Translates messages.', enabled: true },
    { key: 'ai_quiz', label: 'Quizzes', description: 'Teachers draft quizzes.', enabled: false },
  ],
  usage: { since: '2026-10-01', requests: 8, input_tokens: 500, output_tokens: 250, monthly_token_cap: 1000,
           by_feature: [{ feature: 'ai_lesson_plans', label: 'Lesson plans', requests: 5, tokens: 600 }] },
  notice: { version: 1, text: 'AI features send text to a provider. Everything is a draft.', accepted: false, accepted_at: null, accepted_by: null },
};

beforeEach(() => { vi.clearAllMocks(); cleanup(); get.mockResolvedValue({ data: base }); });

describe('AI settings', () => {
  it('shows the provider status, the notice, every feature and this month\'s use', async () => {
    render(<AiSettingsPage />);
    expect(await screen.findByText(/No AI provider is set up/)).toBeTruthy();
    expect(screen.getByText(/Everything is a draft/)).toBeTruthy();
    expect(screen.getByRole('switch', { name: 'Translation' })).toBeTruthy();
    expect(screen.getByText('Lesson plans')).toBeTruthy();
    expect(screen.getByText(/of your/)).toBeTruthy();
    expect(screen.getByText(/75%/)).toBeTruthy();
  });

  it('switching a feature sends just that change and shows the answer', async () => {
    put.mockResolvedValue({ data: { ...base, features: [{ ...base.features[0], enabled: false }, base.features[1]] } });
    render(<AiSettingsPage />);
    fireEvent.click(await screen.findByRole('switch', { name: 'Translation' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/ai/settings/', { features: { ai_translation: false } }));
    await waitFor(() => expect((screen.getByRole('switch', { name: 'Translation' }) as HTMLInputElement).checked).toBe(false));
  });

  it('accepting the notice records it, and the button goes away', async () => {
    post.mockResolvedValue({ data: { ...base, notice: { ...base.notice, accepted: true, accepted_by: 'head@a.test', accepted_at: '2026-10-04T10:00:00Z' } } });
    render(<AiSettingsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /I have read this and accept/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/settings/accept-notice/'));
    expect(await screen.findByText(/Accepted by head@a.test/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /I have read this and accept/ })).toBeNull();
  });

  it('says plainly when nothing has been used yet, and names a connected provider', async () => {
    get.mockResolvedValue({ data: { ...base, provider: { configured: true, name: 'anthropic', note: '' },
      usage: { ...base.usage, requests: 0, input_tokens: 0, output_tokens: 0, monthly_token_cap: 0, by_feature: [] },
      notice: { ...base.notice, accepted: true, accepted_by: 'head@a.test', accepted_at: '2026-10-04T10:00:00Z' } } });
    render(<AiSettingsPage />);
    expect(await screen.findByText('No AI use yet this month.')).toBeTruthy();
    expect(screen.getByText(/anthropic/)).toBeTruthy();
    expect(screen.getByText(/masked before text is sent/)).toBeTruthy();
    expect(screen.queryByText(/monthly allowance/)).toBeNull();
  });
});

describe('The one switch for all AI', () => {
  it('turns every AI feature off and says plainly what that means', async () => {
    put.mockResolvedValue({ data: { ...base, ai_enabled: false } });
    render(<AiSettingsPage />);
    fireEvent.click(await screen.findByRole('switch', { name: 'All AI' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/ai/settings/', { ai_enabled: false }));
    expect(await screen.findByText('AI is switched OFF for your school')).toBeTruthy();
    expect(screen.getByText(/risk scores and flags are hidden/)).toBeTruthy();
  });

  it('shows it on by default and can turn it back on', async () => {
    get.mockResolvedValue({ data: { ...base, ai_enabled: false } });
    put.mockResolvedValue({ data: base });
    render(<AiSettingsPage />);
    fireEvent.click(await screen.findByRole('switch', { name: 'All AI' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/ai/settings/', { ai_enabled: true }));
    expect(await screen.findByText('AI is on for your school')).toBeTruthy();
  });
});

describe('Who approves', () => {
  it('requires two different people', async () => {
    put.mockResolvedValue({ data: { ...base, approval: { ...base.approval, required: 2 } } });
    render(<AiSettingsPage />);
    fireEvent.change(await screen.findByLabelText('Approvals needed'), { target: { value: '2' } });
    await waitFor(() => expect(put).toHaveBeenCalledWith('/ai/settings/', { approval: { required: 2, approvers: [] } }));
  });

  it('names an approver and says who may approve when nobody is named', async () => {
    put.mockResolvedValue({ data: { ...base, approval: { ...base.approval, approvers: ['u2'] } } });
    render(<AiSettingsPage />);
    expect(await screen.findByText(/none named: any administrator/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Approver Deputy'));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/ai/settings/', { approval: { required: 1, approvers: ['u2'] } }));
  });

  it('shows the error when the rule cannot be met', async () => {
    put.mockRejectedValue({ response: { data: { error: 'Two approvals need at least two people who can approve.' } } });
    render(<AiSettingsPage />);
    fireEvent.change(await screen.findByLabelText('Approvals needed'), { target: { value: '2' } });
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
