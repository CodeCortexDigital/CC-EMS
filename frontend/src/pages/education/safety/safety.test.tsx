// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const auth = vi.hoisted(() => ({ role: 'teacher' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: auth.role, user: { email: 'a@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));

import api from '@/services/api';
import SafetyPage from './SafetyPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const task = { id: 't1', incident: 'i1', description: 'Fix the step', owner: 'u2', owner_name: 'Ben Teacher', due_date: '2026-09-01', completed: false, completed_at: null, is_overdue: true };
const incident = {
  id: 'i1', title: 'Fall on stairs', incident_date: '2026-09-30', incident_time: null, place: 'Main stairs', incident_type: 'injury', severity: 'moderate',
  status: 'in_follow_up', students_involved: ['s1'], student_names: ['Ava Brooks'], people_involved: '', description: 'Slipped on a wet step.', witnesses: '',
  action_taken: '', notify_parents: false, parent_notified_at: null, closure_note: '', closed_at: null, reporter_name: 'Ann Teacher', follow_up_tasks: [task], overdue_tasks: 1, created_at: '',
};

function mockApi() {
  get.mockImplementation((url: string) => {
    if (url.endsWith('/incidents/')) return Promise.resolve({ data: [incident] });
    if (url.endsWith('/incidents/i1/')) return Promise.resolve({ data: incident });
    if (url.endsWith('/incidents/owners/')) return Promise.resolve({ data: [{ id: 'u2', name: 'Ben Teacher', role: 'staff' }] });
    if (url.endsWith('/incidents/overdue/')) return Promise.resolve({ data: [{ ...task, incident_title: 'Fall on stairs' }] });
    return Promise.resolve({ data: [] });
  });
  post.mockResolvedValue({ data: {} });
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); auth.role = 'teacher'; mockApi(); });

describe('Safety reports', () => {
  it('a reporter sees their reports but no review tools', async () => {
    render(<SafetyPage />);
    fireEvent.click(await screen.findByText('Fall on stairs'));
    await screen.findByText('Follow-up');
    expect(screen.queryByLabelText('Task')).toBeNull();
    expect(screen.queryByRole('button', { name: /Close incident/ })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Mark done' })).toBeNull();
    expect(get).not.toHaveBeenCalledWith('/auth/safety/incidents/overdue/');   // never asks for the review list
  });

  it('a counsellor sees overdue tasks, adds a follow-up, and must write a note to close', async () => {
    auth.role = 'counsellor';
    render(<SafetyPage />);
    expect(await screen.findByText(/follow-up task is overdue/)).toBeTruthy();
    fireEvent.click(await screen.findByText('Fall on stairs', { selector: 'b' }));
    fireEvent.change(await screen.findByLabelText('Task'), { target: { value: 'Call the parents' } });
    await screen.findByRole('option', { name: 'Ben Teacher' });
    fireEvent.change(screen.getByLabelText('Owner'), { target: { value: 'u2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add task' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/safety/incidents/i1/add_follow_up/', expect.objectContaining({ description: 'Call the parents', owner: 'u2' })));

    fireEvent.click(await screen.findByRole('button', { name: /Close incident…/ }));
    const close = await screen.findByRole('button', { name: 'Close incident' }) as HTMLButtonElement;
    expect(close.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Closure note'), { target: { value: 'Step repaired' } });
    fireEvent.click(close);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/safety/incidents/i1/close/', { closure_note: 'Step repaired' }));
  });

  it('files a report with a title, a description and the students involved', async () => {
    render(<SafetyPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Report an incident/ }));
    const file = await screen.findByRole('button', { name: 'File report' }) as HTMLButtonElement;
    expect(file.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Playground fall' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Tripped on the slide.' } });
    fireEvent.click(screen.getByLabelText('Tell the parents of the students involved') as HTMLElement);
    expect(file.disabled).toBe(false);
    fireEvent.click(file);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/safety/incidents/', expect.objectContaining({ title: 'Playground fall', notify_parents: true, students_involved: [] })));
  });
});
