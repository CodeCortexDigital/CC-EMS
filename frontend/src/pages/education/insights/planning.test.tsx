// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import api from '@/services/api';
import PlanningPage from './PlanningPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const forecast = {
  year: '2026-2027', total: { this_year: 40, expected: 38, low: 35, high: 42 },
  assumptions: { retention: 0.95, retention_assumed: true, conversion: 0.35, conversion_assumed: true, how: 'Next year grade N = ...' },
  unmatched_applications: 2,
  grades: [
    { grade: 5, label: 'Grade 5', this_year: 20, from_below: 18, confirmed: 2, pipeline: 4, expected: 21, low: 19, high: 24, seats: 20, seats_left: -1, sections_needed: 1, class_size: 22 },
    { grade: 6, label: 'Grade 6', this_year: 20, from_below: 19, confirmed: 0, pipeline: 0, expected: 19, low: 17, high: 20, seats: null, seats_left: null, sections_needed: 1, class_size: 20 },
  ],
};
const trends = {
  by: 'subject', terms: [], declining: 1, hidden_groups: 3, min_group: 10, note: 'Groups with fewer than 10 students are not shown.',
  groups: [
    { name: 'Maths', change: -12.5, declining: true, series: [{ term: 't0', term_name: 'Term 1', average: 82, students: 25 }, { term: 't1', term_name: 'Term 2', average: 69.5, students: 25 }] },
    { name: 'Art', change: 3, declining: false, series: [{ term: 't0', term_name: 'Term 1', average: 80, students: 25 }, { term: 't1', term_name: 'Term 2', average: 83, students: 25 }] },
  ],
};
const staffing = {
  staff: [{ teacher_id: 't1', teacher_name: 'Ms Lee', signals: [{ kind: 'credential', label: 'Credential', detail: 'Teaching licence: expired' }] }],
  counts: { credential: 1 }, active_staff: 12, note: 'They are not a rating of anyone\'s work.',
};

function mockApi(over: Record<string, unknown> = {}) {
  get.mockImplementation((url: string) => {
    if (url.includes('forecast')) return Promise.resolve({ data: forecast });
    if (url.includes('trends')) return Promise.resolve({ data: trends });
    if (url.includes('signals')) return over.denied ? Promise.reject({ response: { status: 403 } }) : Promise.resolve({ data: staffing });
    return Promise.resolve({ data: {} });
  });
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); mockApi(); });

describe('Planning page', () => {
  it('shows next year by grade with the range, seats and the assumptions behind it', async () => {
    render(<PlanningPage />);
    expect(await screen.findByText('Grade 5')).toBeTruthy();
    expect(screen.getByText('19–24')).toBeTruthy();
    expect(screen.getByText('no limit set')).toBeTruthy();
    expect(screen.getByText('-1').className).toMatch(/rose/);                       // over capacity stands out
    expect(screen.getByText(/assumed: not enough history yet/)).toBeTruthy();
    expect(screen.getByText(/assumed: not enough decided applications/)).toBeTruthy();
    expect(screen.getByText(/2 application\(s\) name a grade the forecast cannot read/)).toBeTruthy();
  });

  it('shows term-over-term scores, marks a decline, and asks for the other grouping', async () => {
    render(<PlanningPage />);
    expect(await screen.findByText('Maths')).toBeTruthy();
    expect(screen.getByText(/-12.5 pts · declining/)).toBeTruthy();
    expect(screen.getByText(/\+3 pts/).textContent).not.toMatch(/declining/);
    expect(screen.getByText(/fewer than 10 students are not shown/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Group by'), { target: { value: 'class' } });
    await waitFor(() => expect(get).toHaveBeenCalledWith('/auth/insights/trends/', { params: { by: 'class' } }));
  });

  it('lists staff signals with the reminder that it is not a rating, and hides the section if not allowed', async () => {
    const { unmount } = render(<PlanningPage />);
    expect(await screen.findByText('Ms Lee')).toBeTruthy();
    expect(screen.getByText(/not a rating/)).toBeTruthy();
    unmount();
    mockApi({ denied: true });
    render(<PlanningPage />);
    await screen.findByText('Grade 5');
    await waitFor(() => expect(screen.queryByLabelText('Staff signals')).toBeNull());
  });

  it('writes a summary of the chosen report and keeps the figures beside it', async () => {
    post.mockResolvedValue({ data: { report: 'attendance', title: 'Attendance', period: 'x', summary: 'Attendance held steady.', source: 'ai', cached: false,
      facts: [{ label: 'Attendance rate', value: '94%', change: 'down 1 points on the previous period' }] } });
    render(<PlanningPage />);
    await screen.findByText('Grade 5');
    fireEvent.change(screen.getByLabelText('Report'), { target: { value: 'attendance' } });
    fireEvent.click(screen.getByRole('button', { name: /Write the summary/ }));
    expect(await screen.findByText('Attendance held steady.')).toBeTruthy();
    expect(post).toHaveBeenCalledWith('/auth/insights/narrative/', { report: 'attendance' });
    expect(screen.getByText(/Written by AI from the figures below/)).toBeTruthy();
    expect(screen.getByText('Attendance rate:')).toBeTruthy();
  });

  it('says so when the summary is only the figures in words', async () => {
    post.mockResolvedValue({ data: { report: 'overview', title: 'School overview', period: 'x', summary: 'School overview. Students on roll: 40.', source: 'template', facts: [] } });
    render(<PlanningPage />);
    await screen.findByText('Grade 5');
    fireEvent.click(screen.getByRole('button', { name: /Write the summary/ }));
    expect(await screen.findByText(/AI is not set up/)).toBeTruthy();
  });
});
