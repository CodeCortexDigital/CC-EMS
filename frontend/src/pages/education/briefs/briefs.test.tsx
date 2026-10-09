// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/utils/currency', () => ({ formatMoney: (v: number) => `$${v}` }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() } }));

import api from '@/services/api';
import BriefsPage from './BriefsPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;
const patch = api.patch as unknown as ReturnType<typeof vi.fn>;
const put = api.put as unknown as ReturnType<typeof vi.fn>;
const del = api.delete as unknown as ReturnType<typeof vi.fn>;

const brief = (over = {}) => ({
  id: 'b1', status: 'draft', narrative_source: 'template', edited: false, attention_count: 1, approved_at: null, approved_by: '', kind: 'morning', date: '2026-10-12',
  read_by_me: true, read_by: [],
  headline: [
    { key: 'incidents_open', label: 'Safety incidents still open', value: 2, unit: 'count', link: 'safety', attention: true },
    { key: 'fees_overdue_amount_am', label: 'Amount overdue', value: 400, unit: 'money', link: 'finance', attention: false },
  ],
  narrative: 'Morning brief for Monday. Needs attention: safety incidents still open: 2.', original_narrative: 'x', generated_at: '2026-10-12T10:30:00Z',
  attention: [{ key: 'incidents_open', label: 'Safety incidents still open', value: 2, link: 'safety', section: 'Safety & health' }],
  sections: [
    { key: 'safety', title: 'Safety & health', items: [{ key: 'incidents_open', label: 'Safety incidents still open', value: 2, unit: 'count', link: 'safety', attention: true }] },
    { key: 'money', title: 'Money', items: [{ key: 'fees_overdue_amount_am', label: 'Amount overdue', value: 400, unit: 'money', link: 'finance', attention: false }] },
    { key: 'attendance', title: 'Attendance', items: [{ key: 'attendance_rate_prev', label: 'Attendance yesterday', value: null, unit: 'percent', link: 'attendance', attention: false }] },
  ],
  ...over,
});
const settings = { enabled: true, morning_time: '06:30', evening_time: '17:00', retention_days: 92 };
const today = (over = {}) => ({ date: '2026-10-12', morning: null, evening: null, settings, time_zone: 'America/New_York', ...over });
const renderPage = () => render(<MemoryRouter><BriefsPage /></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); cleanup(); vi.spyOn(window, 'confirm').mockReturnValue(true); window.print = vi.fn(); });

describe('Today', () => {
  it('offers to prepare a brief that does not exist yet, and shows the draft it makes', async () => {
    get.mockResolvedValue({ data: today() });
    post.mockResolvedValue({ data: brief() });
    renderPage();
    const prepare = (await screen.findAllByRole('button', { name: /Prepare it now/ }))[0];
    fireEvent.click(prepare);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/briefs/generate/', { kind: 'morning' }));
    expect(await screen.findByText('Draft, not reviewed')).toBeTruthy();
    expect((screen.getByLabelText('Summary text') as HTMLTextAreaElement).value).toMatch(/Needs attention/);
  });

  it('shows what needs attention first, every figure, and says when a figure was not recorded', async () => {
    get.mockResolvedValue({ data: today({ morning: brief() }) });
    renderPage();
    const needs = await screen.findByRole('region', { name: 'Needs attention' });
    expect(within(needs).getByText('Safety incidents still open')).toBeTruthy();
    expect(within(needs).getByRole('link', { name: 'Open' }).getAttribute('href')).toBe('/education/safety');
    expect(screen.getByText('$400')).toBeTruthy();                                // money uses the school currency
    expect(screen.getByText('not recorded')).toBeTruthy();                        // a missing rate is not shown as zero
  });

  it('lets the administrator edit the words and approve, and sends exactly those words', async () => {
    get.mockResolvedValue({ data: today({ morning: brief() }) });
    patch.mockResolvedValue({ data: brief({ narrative: 'My words', edited: true }) });
    post.mockResolvedValue({ data: brief({ narrative: 'My words', edited: true, status: 'approved', approved_by: 'Head', approved_at: '2026-10-12T11:00:00Z' }) });
    renderPage();
    const box = await screen.findByLabelText('Summary text');
    fireEvent.change(box, { target: { value: 'My words' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save my edits' }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith('/auth/briefs/b1/', { narrative: 'My words' }));
    fireEvent.click(screen.getByRole('button', { name: /Approve/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/briefs/b1/approve/', { narrative: 'My words' }));
    expect(await screen.findByText(/Approved by Head/)).toBeTruthy();
  });

  it('an approved brief is locked: no text box, no approve or edit buttons, but it can be printed and deleted', async () => {
    get.mockResolvedValue({ data: today({ morning: brief({ status: 'approved', approved_by: 'Head', approved_at: '2026-10-12T11:00:00Z' }) }) });
    del.mockResolvedValue({});
    renderPage();
    await screen.findByText(/Approved by Head/);
    expect(screen.queryByLabelText('Summary text')).toBeNull();
    expect(screen.queryByRole('button', { name: /^Approve/ })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Save my edits' })).toBeNull();
    expect(screen.queryByRole('button', { name: /Prepare again/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Print/ }));
    expect(window.print).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Delete/ }));
    await waitFor(() => expect(del).toHaveBeenCalledWith('/auth/briefs/b1/'));
  });

  it('says plainly whether the words came from AI', async () => {
    get.mockResolvedValue({ data: today({ morning: brief({ narrative_source: 'ai' }) }) });
    renderPage();
    expect(await screen.findByText('Words written by AI')).toBeTruthy();
    expect(screen.getByText(/counts only, no names/)).toBeTruthy();
  });
});

describe('Headlines and read stamps', () => {
  it('shows the headline figures on one screen and can switch back to the full detail', async () => {
    get.mockResolvedValue({ data: today({ morning: brief() }) });
    renderPage();
    await screen.findByRole('region', { name: 'Safety & health' });
    fireEvent.click(screen.getByRole('button', { name: 'Headlines' }));
    const tiles = screen.getByRole('region', { name: 'Headlines' });
    expect(within(tiles).getByText('2')).toBeTruthy();
    expect(within(tiles).getByText('$400')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Safety & health' })).toBeNull();           // the detail is hidden, the approval controls are not
    expect(screen.getByRole('button', { name: /Approve/ })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Full detail' }));
    expect(await screen.findByRole('region', { name: 'Safety & health' })).toBeTruthy();
  });

  it('marks a brief as read and then shows who has read it', async () => {
    get.mockResolvedValue({ data: today({ morning: brief({ read_by_me: false }) }) });
    post.mockResolvedValue({ data: brief({ read_by_me: true, read_by: [{ name: 'Head', at: '2026-10-12T11:05:00Z' }] }) });
    renderPage();
    expect(await screen.findByText('Unread')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Mark as read' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/briefs/b1/read/', {}));
    expect(await screen.findByLabelText('Read by')).toBeTruthy();
    expect(screen.getByLabelText('Read by').textContent).toMatch(/Read by Head/);
    expect(screen.queryByText('Unread')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Mark as read' })).toBeNull();
  });

  it('flags unread days in the history list', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/today/') ? today() : [
      { id: 'b1', status: 'approved', narrative_source: 'ai', edited: false, attention_count: 0, approved_at: null, approved_by: 'Head', read_by_me: false, kind: 'evening', date: '2026-10-11' },
      { id: 'b2', status: 'approved', narrative_source: 'ai', edited: false, attention_count: 0, approved_at: null, approved_by: 'Head', read_by_me: true, kind: 'morning', date: '2026-10-11' },
    ] }));
    renderPage();
    fireEvent.click(await screen.findByRole('tab', { name: 'Daily history' }));
    await screen.findByText(/Evening summary/);
    expect(screen.getAllByText('Unread')).toHaveLength(1);
  });
});

describe('History, roll-ups and settings', () => {
  it('lists the kept daily briefs and opens one', async () => {
    get.mockImplementation((url: string) => {
      if (url.endsWith('/today/')) return Promise.resolve({ data: today() });
      if (/\/briefs\/b1\/$/.test(url)) return Promise.resolve({ data: brief() });
      return Promise.resolve({ data: [{ id: 'b1', status: 'approved', narrative_source: 'ai', edited: false, attention_count: 2, approved_at: null, approved_by: 'Head', read_by_me: true, kind: 'evening', date: '2026-10-11' }] });
    });
    renderPage();
    fireEvent.click(await screen.findByRole('tab', { name: 'Daily history' }));
    const row = await screen.findByText(/Evening summary/);
    expect(screen.getByText('2 to look at')).toBeTruthy();
    fireEvent.click(row);
    expect(await screen.findByLabelText('Needs attention')).toBeTruthy();
  });

  it('builds a roll-up from the daily briefs and tells you when there is nothing to build from', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/today/') ? today() : [] }));
    post.mockRejectedValueOnce({ response: { data: { error: 'There are no daily briefs in that period to roll up.' } } });
    renderPage();
    fireEvent.click(await screen.findByRole('tab', { name: 'Weekly, fortnightly, monthly' }));
    expect(await screen.findByText(/No roll-ups yet/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Build the latest weekly brief/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/briefs/rollups/generate/', { period: 'week' }));
    const sonner = await import('sonner');
    await waitFor(() => expect(sonner.toast.error).toHaveBeenCalledWith('There are no daily briefs in that period to roll up.'));
  });

  it('saves the times and says how long things are kept', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/today/') ? today() : settings }));
    put.mockResolvedValue({ data: { ...settings, morning_time: '07:15' } });
    renderPage();
    fireEvent.click(await screen.findByRole('tab', { name: 'Settings' }));
    expect(await screen.findByText(/kept for 92 days/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Morning time'), { target: { value: '07:15' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/auth/briefs/settings/', { enabled: true, morning_time: '07:15', evening_time: '17:00' }));
  });
});
