// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

import api from '@/services/api';
import { toast } from 'sonner';
import AiGovernancePage from './AiGovernancePage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;
const del = api.delete as unknown as ReturnType<typeof vi.fn>;

const request = (over = {}) => ({
  id: 'r1', action: 'send_fee_reminder', label: 'Send a fee reminder', summary: 'Send a fee reminder for invoice INV-7 (Amy Alder) to the family', status: 'pending',
  requested_by: 'Amy Accountant', requester_role: 'accountant', created_at: '2026-10-22T10:00:00Z', expires_at: '2026-10-24T10:00:00Z',
  decided_by: '', decided_at: null, decision_note: '', result: {}, approver_roles: ['admin'], can_decide: true, ...over,
});
const doc = (over = {}) => ({ id: 'd1', title: 'Late policy', audience: 'everyone', is_active: true, passages: 2, characters: 300, updated_at: '2026-10-22T10:00:00Z', ...over });

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('Approvals', () => {
  it('shows what is waiting, who asked, and nothing as done', async () => {
    get.mockResolvedValue({ data: [request()] });
    render(<AiGovernancePage />);
    expect(await screen.findByText(/invoice INV-7/)).toBeTruthy();
    expect(screen.getByText('Waiting for approval')).toBeTruthy();
    expect(screen.getByText(/Asked by Amy Accountant \(accountant\)/)).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/ai/governance/approvals/', { params: { status: 'pending' } });
  });

  it('approving sends the note and reports the result', async () => {
    get.mockResolvedValue({ data: [request()] });
    post.mockResolvedValue({ data: request({ status: 'executed', result: { note: '1 message(s) queued to the family.' } }) });
    render(<AiGovernancePage />);
    fireEvent.change(await screen.findByLabelText(/Note for/), { target: { value: 'Go ahead' } });
    fireEvent.click(screen.getByText(/Approve and run/));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/governance/approvals/r1/approve/', { note: 'Go ahead' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('1 message(s) queued to the family.'));
  });

  it('rejecting says nothing was done', async () => {
    get.mockResolvedValue({ data: [request()] });
    post.mockResolvedValue({ data: request({ status: 'rejected' }) });
    render(<AiGovernancePage />);
    fireEvent.click(await screen.findByText('Reject'));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/governance/approvals/r1/reject/', { note: '' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Rejected. Nothing was done.'));
  });

  it('an approval that fails is shown as an error with the reason', async () => {
    get.mockResolvedValue({ data: [request()] });
    post.mockResolvedValue({ data: request({ status: 'failed', result: { error: 'Invoice INV-7 has nothing left to pay, so no reminder is needed.' } }) });
    render(<AiGovernancePage />);
    fireEvent.click(await screen.findByText(/Approve and run/));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('nothing left to pay')));
  });

  it('a request that cannot be decided by this person has no buttons, and decided ones show who decided', async () => {
    get.mockResolvedValue({ data: [request({ can_decide: false }), request({ id: 'r2', status: 'executed', decided_by: 'Head', decision_note: 'ok', result: { note: 'Done.' }, can_decide: false })] });
    render(<AiGovernancePage />);
    await screen.findAllByTestId('approval-row');
    expect(screen.queryByText(/Approve and run/)).toBeNull();
    expect(screen.getByText(/Decided by Head/)).toBeTruthy();
  });

  it('can include decided requests', async () => {
    get.mockResolvedValue({ data: [] });
    render(<AiGovernancePage />);
    expect(await screen.findByText('Nothing is waiting for approval.')).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Also show decided/));
    await waitFor(() => expect(get).toHaveBeenCalledWith('/ai/governance/approvals/', { params: { status: 'all' } }));
  });
});

describe('School documents', () => {
  const openDocs = async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.includes('knowledge') ? [doc()] : [] }));
    render(<AiGovernancePage />);
    fireEvent.click(await screen.findByRole('tab', { name: 'School documents' }));
    await screen.findByText('Late policy');
  };

  it('lists documents with their audience', async () => {
    await openDocs();
    expect(screen.getByText(/Everyone, 2 passages/)).toBeTruthy();
  });

  it('adds a document', async () => {
    await openDocs();
    post.mockResolvedValue({ data: doc() });
    fireEvent.click(screen.getByText('Add a document'));
    fireEvent.change(screen.getByPlaceholderText(/Student handbook/), { target: { value: 'Uniform' } });
    fireEvent.change(screen.getByLabelText('Document text'), { target: { value: 'Navy sweater and grey trousers for every student.' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/governance/knowledge/', { title: 'Uniform', body: 'Navy sweater and grey trousers for every student.', audience: 'everyone' }));
  });

  it('will not save a document with almost no text', async () => {
    await openDocs();
    fireEvent.click(screen.getByText('Add a document'));
    fireEvent.change(screen.getByPlaceholderText(/Student handbook/), { target: { value: 'Uniform' } });
    expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
  });

  it('deletes only after confirmation', async () => {
    await openDocs();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    del.mockResolvedValue({});
    fireEvent.click(screen.getByLabelText('Delete Late policy'));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('Delete Late policy'));
    await waitFor(() => expect(del).toHaveBeenCalledWith('/ai/governance/knowledge/d1/'));
    confirm.mockRestore();
  });

  it('tries a question as a chosen role and shows the passage with its title', async () => {
    await openDocs();
    post.mockResolvedValue({ data: { as_role: 'parent', passages: [{ document_id: 'd1', title: 'Late policy', ordinal: 1, text: 'Arrive before 8:15.', score: 2 }] } });
    fireEvent.change(screen.getByLabelText('Question to try'), { target: { value: 'when is late' } });
    fireEvent.change(screen.getByLabelText('Ask as'), { target: { value: 'parent' } });
    fireEvent.click(screen.getByText('Search'));
    expect(await screen.findByText('Arrive before 8:15.')).toBeTruthy();
    expect(post).toHaveBeenCalledWith('/ai/governance/knowledge/search/', { query: 'when is late', as_role: 'parent' });
  });

  it('says when nothing matches', async () => {
    await openDocs();
    post.mockResolvedValue({ data: { as_role: 'admin', passages: [] } });
    fireEvent.change(screen.getByLabelText('Question to try'), { target: { value: 'moon base' } });
    fireEvent.click(screen.getByText('Search'));
    expect(await screen.findByText(/Nothing matches/)).toBeTruthy();
  });
});
