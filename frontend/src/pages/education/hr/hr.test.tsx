// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const role = vi.hoisted(() => ({ current: 'teacher' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: role.current, user: { email: 'ann@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import api from '@/services/api';
import hr, { errorText, leaveTypeLabel, LEAVE_TYPES } from '@/services/hr.service';
import CoverRequestsPage from './CoverRequestsPage';
import PayrollSetupPage from './PayrollSetupPage';
import { MyHrPanel } from './MyHrPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const openRequest = {
  id: 'r1', date: '2099-01-05', status: 'open', requester: { id: 't1', name: 'Ann Math' }, substitute: null,
  period: { id: 'p1', name: 'Period 1', number: 1, start: '08:00', end: '08:45' }, class_name: 'Grade 5', subject: 'Mathematics',
  description: 'Grade 5 Mathematics', reason: 'Dentist', filled_how: '', filled_at: null, created_at: '', can_accept: true,
  can_cancel: false, is_mine: false, is_covering: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  role.current = 'teacher';
});

describe('hr.service', () => {
  it('reads the most useful message out of an API error', () => {
    expect(errorText({ response: { data: { error: 'Not free.' } } }, 'x')).toBe('Not free.');
    expect(errorText({ response: { data: { detail: 'Nope' } } }, 'x')).toBe('Nope');
    expect(errorText({ response: { data: { rating: ['Rating must be from 1 to 5.'] } } }, 'x')).toBe('Rating must be from 1 to 5.');
    expect(errorText(new Error('boom'), 'fallback')).toBe('fallback');
  });

  it('knows the US leave types and labels them', () => {
    expect(LEAVE_TYPES.map((t) => t.key)).toEqual(expect.arrayContaining(['personal', 'bereavement', 'jury', 'professional', 'unpaid']));
    expect(leaveTypeLabel('jury')).toBe('Jury duty');
    expect(leaveTypeLabel('mystery')).toBe('mystery');
  });

  it('posts cover actions to the right place', async () => {
    post.mockResolvedValue({ data: openRequest });
    await hr.cover.act('r1', 'assign', { teacher_id: 't9' });
    expect(post).toHaveBeenCalledWith('/auth/hr/cover/r1/assign/', { teacher_id: 't9' });
  });
});

describe('CoverRequestsPage', () => {
  it('lets a free colleague take an open period', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/directory/') ? [] : [openRequest] }));
    post.mockResolvedValue({ data: { ...openRequest, status: 'filled' } });
    render(<MemoryRouter><CoverRequestsPage /></MemoryRouter>);

    expect(await screen.findByText(/Period 1 \(08:00-08:45\)/)).toBeTruthy();
    expect(screen.getByText(/Ann Math is away: Dentist/)).toBeTruthy();
    expect(screen.queryByText('Assign')).toBeNull(); // only HR can assign

    fireEvent.click(screen.getByText('I can cover'));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/hr/cover/r1/accept/', {}));
  });

  it('shows HR the assign button and every request', async () => {
    role.current = 'hr';
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/directory/') ? [] : [{ ...openRequest, can_accept: false }] }));
    render(<MemoryRouter><CoverRequestsPage /></MemoryRouter>);
    expect(await screen.findByText('Assign')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/auth/hr/cover/', { params: expect.objectContaining({ scope: 'all' }) });
  });

  it('tells a teacher with nothing to cover that nothing needs them', async () => {
    get.mockResolvedValue({ data: [] });
    render(<MemoryRouter><CoverRequestsPage /></MemoryRouter>);
    expect(await screen.findByText(/Nothing needs you right now/)).toBeTruthy();
  });
});

describe('PayrollSetupPage', () => {
  it('is closed to teachers and managers', () => {
    render(<PayrollSetupPage />);
    expect(screen.getByText(/open to administrators and HR only/)).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });

  it('shows HR what each payslip would start from', async () => {
    role.current = 'hr';
    get.mockImplementation((url: string) => Promise.resolve({
      data: url.endsWith('/grades/') ? [{ id: 'g1', name: 'Teacher L2', base_salary: '3000', notes: '', people: 1 }]
        : [{ teacher_id: 't1', name: 'Ann Math', employee_id: 'E1', role: 'Teacher', department: '', pay_grade: 'g1', pay_grade_name: 'Teacher L2',
          tax_rate_percent: 10, benefits: [], monthly_salary: null, basic: 3000, allowances: 200, benefit_deductions: 100, tax: 320, deductions: 420, net: 2780 }],
    }));
    render(<PayrollSetupPage />);
    expect(await screen.findByText('Ann Math')).toBeTruthy();
    expect(screen.getAllByText(/Teacher L2/).length).toBeGreaterThan(0);
    expect(screen.getByText(/\(10%\)/)).toBeTruthy();
  });
});

describe('MyHrPanel', () => {
  it('explains when the login has no staff record', async () => {
    get.mockResolvedValue({ data: { linked: false } });
    render(<MemoryRouter><MyHrPanel /></MemoryRouter>);
    expect(await screen.findByText(/not linked to a staff record/)).toBeTruthy();
  });

  it('lets a new hire tick off onboarding and warns about shared reviews', async () => {
    get.mockResolvedValue({
      data: {
        linked: true, teacher: { id: 't1', name: 'Dana New', role: 'Science teacher', department: 'Science', manager: { id: 'm', name: 'Head Teacher' } },
        contracts: [], credentials: [], goals: [], cover: [],
        reviews: [{ id: 'v1', status: 'shared' }],
        onboarding: [{ id: 'o1', teacher: 't1', teacher_name: 'Dana New', title: 'Sign contract', due_date: null, done: false, done_at: null, order: 0 }],
      },
    });
    (api.patch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    render(<MemoryRouter><MyHrPanel /></MemoryRouter>);
    expect(await screen.findByText(/Reports to Head Teacher/)).toBeTruthy();
    expect(screen.getByText(/1 review shared with you/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Sign contract'));
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/auth/hr/onboarding/o1/', { done: true }));
  });
});
