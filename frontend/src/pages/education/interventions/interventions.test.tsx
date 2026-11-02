// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const auth = vi.hoisted(() => ({ role: 'counsellor' as string, id: 'u-carol' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: auth.role, user: { id: auth.id, email: 'x@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));

import api from '@/services/api';
import InterventionsPage from './InterventionsPage';
import EscalationLadder from '@/components/attendance/EscalationLadder';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;
const patch = api.patch as unknown as ReturnType<typeof vi.fn>;

const item = (over = {}) => ({
  id: 'i1', student: 's1', student_name: 'Noah Smith', student_number: 'STU1', class_name: 'Grade 4', source: 'absence', title: '5 unexcused absences in 30 days',
  description: 'Noah reached the 5-absence step.', suggested_actions: ['Call the family', 'Agree a plan'], status: 'open', priority: 'normal', owner: null, owner_name: '',
  due_date: '2026-10-09', is_overdue: false, notes: [], created_at: '2026-10-02T10:00:00Z', closed_at: null, closure_note: '',
  started_on: null, sessions_delivered: 0, outcome: '', evidence: '', review_on: null, is_review_due: false, ...over,
});
const reach = { raised: 5, students_flagged: 4, students_reached: 3, sessions_delivered: 9, average_days_to_start: 2.5, closed: 2, results: { improved: 1, no_change: 1, worse: 0, not_measured: 0 }, closed_without_result: 0, reviews_due: 1 };
const summary = { open: 3, in_progress: 1, overdue: 2, unassigned: 1, mine: 0, high_priority: 1 };

function mockApi(list = [item()]) {
  get.mockImplementation((url: string) => {
    if (url.endsWith('/summary/')) return Promise.resolve({ data: summary });
    if (url.endsWith('/reach/')) return Promise.resolve({ data: reach });
    if (url.endsWith('/owners/')) return Promise.resolve({ data: [{ id: 'u-ann', name: 'Ann Teacher', role: 'staff' }] });
    if (url.endsWith('/lookup/')) return Promise.resolve({ data: [{ id: 's1', student_id: 'STU1', name: 'Noah Smith', class_name: 'Grade 4' }] });
    if (/\/interventions\/i1\/$/.test(url)) return Promise.resolve({ data: list[0] });
    return Promise.resolve({ data: list });
  });
  post.mockResolvedValue({ data: {} });
  patch.mockResolvedValue({ data: {} });
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); auth.role = 'counsellor'; auth.id = 'u-carol'; mockApi(); });

describe('Record of support', () => {
  it('shows who the support reached and what came of it', async () => {
    render(<InterventionsPage />);
    const panel = await screen.findByRole('region', { name: 'Reach and results' });
    expect(panel.textContent).toContain('Students reached');
    expect(panel.textContent).toContain('9');
    expect(panel.textContent).toContain('1 improved, 1 no change');
  });

  it('shows the start date, sessions, result and review date of one, and logs a session', async () => {
    mockApi([item({ status: 'in_progress', started_on: '2026-10-05', sessions_delivered: 3, outcome: 'improved', evidence: 'Absences 6 to 1', review_on: '2026-11-01', is_review_due: true })]);
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    const record = await screen.findByLabelText('Record of support');
    expect(record.textContent).toContain('Sessions delivered3');
    expect(record.textContent).toContain('Improved');
    expect(record.textContent).toContain('Absences 6 to 1');
    fireEvent.click(screen.getByRole('button', { name: 'Log a session' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/interventions/i1/log_session/'));
  });

  it('sends the result and evidence when finishing', async () => {
    mockApi([item({ status: 'in_progress' })]);
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    fireEvent.click(await screen.findByRole('button', { name: 'Mark done…' }));
    fireEvent.change(screen.getByLabelText('What was done'), { target: { value: 'Met weekly' } });
    fireEvent.change(screen.getByLabelText('Result'), { target: { value: 'improved' } });
    fireEvent.change(screen.getByLabelText('Evidence'), { target: { value: 'Absences 6 to 1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Mark done' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/interventions/i1/complete/', { note: 'Met weekly', outcome: 'improved', evidence: 'Absences 6 to 1' }));
  });
});

describe('Interventions (counselor)', () => {
  it('shows the numbers, the list, and what each one is for', async () => {
    render(<InterventionsPage />);
    expect(await screen.findByText('Noah Smith')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Open: 4' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Overdue: 2' })).toBeTruthy();
    expect(screen.getByText('Attendance')).toBeTruthy();
    expect(screen.getByText('No owner', { exact: false })).toBeTruthy();
  });

  it('a tile switches to that view and asks the server for it', async () => {
    render(<InterventionsPage />);
    await screen.findByText('Noah Smith');
    fireEvent.click(screen.getByRole('button', { name: 'Overdue: 2' }));
    await waitFor(() => expect(get).toHaveBeenCalledWith('/auth/interventions/', { params: expect.objectContaining({ overdue: '1' }) }));
    fireEvent.click(screen.getByRole('button', { name: 'Unassigned' }));
    await waitFor(() => expect(get).toHaveBeenCalledWith('/auth/interventions/', { params: expect.objectContaining({ owner: 'none', active: '1' }) }));
  });

  it('opens one, shows the suggested steps, and assigns an owner', async () => {
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    expect(await screen.findByText('Suggested next steps')).toBeTruthy();
    expect(screen.getByText('Call the family')).toBeTruthy();
    await screen.findByRole('option', { name: 'Ann Teacher' });
    fireEvent.change(screen.getByLabelText('Assign to'), { target: { value: 'u-ann' } });
    await waitFor(() => expect(patch).toHaveBeenCalledWith('/auth/interventions/i1/', { owner: 'u-ann' }));
  });

  it('cannot be marked done without saying what was done', async () => {
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    fireEvent.click(await screen.findByRole('button', { name: 'Mark done…' }));
    const go = screen.getByRole('button', { name: 'Mark done' }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('What was done'), { target: { value: 'Met with the family, plan agreed' } });
    fireEvent.click(go);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/interventions/i1/complete/', { note: 'Met with the family, plan agreed' }));
  });

  it('a closed one can be reopened but not worked on', async () => {
    mockApi([item({ status: 'done', closed_at: '2026-10-03T10:00:00Z', closure_note: 'ok' })]);
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    expect(await screen.findByRole('button', { name: 'Reopen' })).toBeTruthy();
    expect(screen.queryByLabelText('Add a note')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Mark done…' })).toBeNull();
  });

  it('adds one by hand for a student', async () => {
    render(<InterventionsPage />);
    await screen.findByText('Noah Smith');
    fireEvent.click(screen.getByRole('button', { name: /New intervention/ }));
    const add = await screen.findByRole('button', { name: 'Add' }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText('Find the student'), { target: { value: 'noah' } });
    fireEvent.click(await screen.findByRole('option', { name: /Noah Smith/ }));
    fireEvent.change(await screen.findByLabelText('Title'), { target: { value: 'Check in about mornings' } });
    expect(add.disabled).toBe(false);
    fireEvent.click(add);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/interventions/', expect.objectContaining({ student: 's1', title: 'Check in about mornings', priority: 'normal', owner: null })));
  });
});

describe('Interventions (assigned staff member)', () => {
  beforeEach(() => { auth.role = 'teacher'; auth.id = 'u-ann'; });

  it('sees only their own list, with no tiles and no way to add or reassign', async () => {
    mockApi([item({ owner: 'u-ann', owner_name: 'Ann Teacher' })]);
    render(<InterventionsPage />);
    expect(await screen.findByText('Noah Smith')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/auth/interventions/', { params: expect.objectContaining({ owner: 'me' }) });
    expect(screen.queryByRole('button', { name: /New intervention/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Open:/ })).toBeNull();
    fireEvent.click(screen.getByText('Noah Smith'));
    expect(await screen.findByLabelText('Add a note')).toBeTruthy();
    expect(screen.queryByLabelText('Assign to')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Dismiss…' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Mark done…' })).toBeTruthy();
  });

  it('cannot work on one that is not theirs', async () => {
    mockApi([item({ owner: 'someone-else', owner_name: 'Ben Teacher' })]);
    render(<InterventionsPage />);
    fireEvent.click(await screen.findByText('Noah Smith'));
    await screen.findByText('Suggested next steps');
    expect(screen.queryByLabelText('Add a note')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Mark done…' })).toBeNull();
  });
});

describe('Absence ladder editor', () => {
  const steps = [{ count: 3, days: 30, staff: false, intervention: false }, { count: 5, days: 30, staff: true, intervention: true }];

  it('shows each step, and only offers to go back when the ladder is custom', () => {
    const { rerender } = render(<EscalationLadder steps={steps} isCustom={false} onSave={() => undefined} onReset={() => undefined} />);
    expect((screen.getByLabelText('Step 2 absences') as HTMLInputElement).value).toBe('5');
    expect((screen.getByLabelText('Step 2 open an intervention') as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByRole('button', { name: /Back to the usual steps/ })).toBeNull();
    rerender(<EscalationLadder steps={steps} isCustom onSave={() => undefined} onReset={() => undefined} />);
    expect(screen.getByRole('button', { name: /Back to the usual steps/ })).toBeTruthy();
  });

  it('saves only after a change, sorted, and refuses two steps with the same number', () => {
    const onSave = vi.fn();
    render(<EscalationLadder steps={steps} isCustom onSave={onSave} onReset={() => undefined} />);
    const save = screen.getByRole('button', { name: 'Save ladder' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);                                             // nothing changed
    fireEvent.click(screen.getByRole('button', { name: /Add a step/ }));
    fireEvent.change(screen.getByLabelText('Step 3 absences'), { target: { value: '5' } });
    expect(screen.getByRole('alert').textContent).toMatch(/same number/);
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Step 3 absences'), { target: { value: '2' } });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith([
      { count: 2, days: 30, staff: true, intervention: false }, steps[0], steps[1],
    ]);
  });

  it('removing every step is allowed and says families will not be warned', () => {
    render(<EscalationLadder steps={steps} isCustom onSave={() => undefined} onReset={() => undefined} />);
    fireEvent.click(screen.getByLabelText('Remove step 1'));
    fireEvent.click(screen.getByLabelText('Remove step 1'));
    expect(screen.getByText(/families are not warned/)).toBeTruthy();
  });

  it('keeps a step\'s number and days within sensible limits', () => {
    render(<EscalationLadder steps={steps} isCustom onSave={() => undefined} onReset={() => undefined} />);
    fireEvent.change(screen.getByLabelText('Step 1 days'), { target: { value: '2' } });
    expect((screen.getByRole('button', { name: 'Save ladder' }) as HTMLButtonElement).disabled).toBe(true);
  });
});
