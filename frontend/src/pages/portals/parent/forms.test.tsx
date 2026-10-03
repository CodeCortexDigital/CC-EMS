// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: 'parent', user: { email: 'mom@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));

import api from '@/services/api';
import ParentFormsPage from './ParentFormsPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const base = { template: 't1', title: 'Zoo trip', student: 's1', student_name: 'Ava Brooks', class_name: 'Grade 5', due_date: '2026-10-20', signed_at: null, signer_name: '' };
const waiting = { ...base, id: 'a1', status: 'pending' };
const done = { ...base, id: 'a2', student: 's2', student_name: 'Ben Brooks', status: 'signed', signed_at: '2026-10-01T10:00:00Z', signer_name: 'Erin Brooks' };
const detail = {
  ...waiting, body: 'I allow my child to go on the zoo trip.',
  questions: [
    { id: 'emergency', label: 'Emergency contact is current?', type: 'yes_no', options: [], required: true },
    { id: 'bus', label: 'Travel by', type: 'choice', options: ['School bus', 'Parent car'], required: true },
    { id: 'allergy', label: 'Any allergies?', type: 'text', options: [], required: false },
  ],
};

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/my/') ? [waiting, done] : url.endsWith('/my/a1/') ? detail : { ...done, body: 'Text', questions: [], answers: {} } }));
  post.mockResolvedValue({ data: { ...waiting, status: 'signed' } });
});

describe('Forms to sign', () => {
  it('separates what is waiting from what is done', async () => {
    render(<ParentFormsPage />);
    expect(await screen.findByText('Waiting for you')).toBeTruthy();
    expect(screen.getByText(/For Ava Brooks/)).toBeTruthy();
    expect(screen.getByText(/Signed/)).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Read and sign' })).toHaveLength(1);
  });

  it('cannot be signed until the name, the tick box and every required answer are given', async () => {
    render(<ParentFormsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Read and sign' }));
    const sign = await screen.findByRole('button', { name: 'Sign' }) as HTMLButtonElement;
    expect(sign.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText('Your full name'), { target: { value: 'Erin Brooks' } });
    fireEvent.click(screen.getByRole('checkbox'));
    expect(sign.disabled).toBe(true);                                   // required questions still unanswered
    fireEvent.click(screen.getByLabelText('Yes'));
    fireEvent.change(screen.getByLabelText('Travel by'), { target: { value: 'Parent car' } });
    expect(sign.disabled).toBe(false);

    fireEvent.click(sign);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/forms/my/a1/sign/', {
      signer_name: 'Erin Brooks', agree: true, decision: 'signed', answers: { emergency: 'yes', bus: 'Parent car' },
    }));
  });

  it('a family can decline without answering the questions', async () => {
    render(<ParentFormsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Read and sign' }));
    fireEvent.change(await screen.findByLabelText('Your full name'), { target: { value: 'Erin Brooks' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'I do not agree' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/forms/my/a1/sign/', expect.objectContaining({ decision: 'declined', answers: {} })));
  });

  it('a form that is already signed is read only and says it cannot be changed', async () => {
    render(<ParentFormsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'View' }));
    expect(await screen.findByText(/A signed form cannot be changed/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Sign' })).toBeNull();
  });
});
