// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const role = vi.hoisted(() => ({ current: 'teacher' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: role.current }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/class.service', () => ({ default: { getAll: vi.fn().mockResolvedValue({ data: [{ id: 'c1', name: '6年' }] }) } }));
vi.mock('@/services/termReports.service', async (orig) => {
  const actual = await orig<typeof import('@/services/termReports.service')>();
  return { ...actual, default: { layouts: vi.fn(), saveLayout: vi.fn(), roster: vi.fn(), open: vi.fn(), get: vi.fn(), save: vi.fn(), prefill: vi.fn(), finalise: vi.fn(), reopen: vi.fn() } };
});

import termReports, { LayoutConfig, TermReport } from '@/services/termReports.service';
import TermReportsPage from './TermReportsPage';
import TermReportEditorPage from './TermReportEditorPage';
import { TermReportPrint } from './TermReportPrintPage';

const m = termReports as unknown as Record<string, ReturnType<typeof vi.fn>>;

const config: LayoutConfig = {
  title: '通知表', scale: 'abc', viewpoints: true, subjects: ['国語', '算数'], conduct_items: ['責任感'], comment_fields: [{ key: 'homeroom', label: '担任からの所見' }],
  sections: { attendance: true, conduct: true, comments: true }, thresholds: { abc: [80, 50], five: [90, 75, 60, 40] },
};
const report = (over: Partial<TermReport> = {}): TermReport => ({
  id: 'r1', student: 's1', student_name: '山田 太郎', student_number: 'W-001', layout: config, term: 't1', year_label: '2026年度', term_label: '1学期',
  class_name: '6年1組', teacher_name: '佐藤 花', principal_name: '鈴木 一郎', school_days: 70, suspended_days: 0, absent_days: 2, attendance_remarks: '',
  content: { subjects: { 国語: { v1: 'A', v2: 'B', v3: 'A', rating: 'A' }, 算数: { rating: '' } }, conduct: { 責任感: true }, comments: { homeroom: 'よくがんばりました。' } },
  is_locked: false, finalised_at: null, finalised_by: '', school_name: '若葉学園', ...over,
});

beforeEach(() => { vi.clearAllMocks(); cleanup(); role.current = 'teacher'; });

describe('Term reports page', () => {
  const roster = { year: '2026年度', terms: [{ id: 't1', name: '1学期' }, { id: 't2', name: '2学期' }],
                   results: [{ student: 's1', student_number: 'W-001', student_name: '山田 太郎', report_id: null, is_locked: false },
                             { student: 's2', student_number: 'W-002', student_name: '山田 花子', report_id: 'r2', is_locked: true }] };

  it('lists the students of a class with the state of each report, and opens one', async () => {
    m.roster.mockResolvedValue(roster);
    m.open.mockResolvedValue(report());
    render(<MemoryRouter initialEntries={['/education/term-reports']}><Routes>
      <Route path="/education/term-reports" element={<TermReportsPage />} /><Route path="/education/term-reports/:id" element={<p>EDITOR</p>} /></Routes></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText(/^Class/), { target: { value: 'c1' } });
    expect(await screen.findByText('山田 花子')).toBeTruthy();
    expect(screen.getByText('Not started')).toBeTruthy();
    expect(screen.getByText('Finalised')).toBeTruthy();
    fireEvent.click(screen.getByText('Start report'));
    await waitFor(() => expect(m.open).toHaveBeenCalledWith('s1', 't1'));
    expect(await screen.findByText('EDITOR')).toBeTruthy();
  });

  it('shows the layout editor to administrators only', async () => {
    m.roster.mockResolvedValue(roster);
    m.layouts.mockResolvedValue({ layouts: [{ id: 'l1', name: '小学校 通知表', level: 'elementary', is_default: true, config }], scales: { abc: 'A・B・C', five: '5段階', percent: '点数' }, viewpoints: [] });
    m.saveLayout.mockResolvedValue({ id: 'l1', name: '若葉 通知表', level: 'elementary', is_default: true, config });
    render(<MemoryRouter><TermReportsPage /></MemoryRouter>);
    await screen.findByText('Term reports (通知表)');
    expect(screen.queryByText('Edit the layout')).toBeNull();
    cleanup();
    role.current = 'admin';
    render(<MemoryRouter><TermReportsPage /></MemoryRouter>);
    fireEvent.click(await screen.findByText('Edit the layout'));
    const subjects = await screen.findByLabelText(/^Subjects/);
    expect((subjects as HTMLTextAreaElement).value).toBe('国語\n算数');
    fireEvent.change(subjects, { target: { value: '国語\n算数\n理科' } });
    fireEvent.click(screen.getByText('Save the layout'));
    await waitFor(() => expect(m.saveLayout).toHaveBeenCalledWith(expect.objectContaining({ id: 'l1', config: expect.objectContaining({ subjects: ['国語', '算数', '理科'] }) })));
  });
});

describe('Term report editor', () => {
  const open = async (r = report()) => {
    m.get.mockResolvedValue(r);
    render(<MemoryRouter initialEntries={['/education/term-reports/r1']}><Routes><Route path="/education/term-reports/:id" element={<TermReportEditorPage />} /></Routes></MemoryRouter>);
    await screen.findByText(/山田 太郎 · 1学期/);
  };

  it('shows a row for each subject of the layout with its viewpoints and rating', async () => {
    await open();
    expect(screen.getByLabelText('国語 rating')).toHaveProperty('value', 'A');
    expect(screen.getByLabelText('算数 知識・技能')).toBeTruthy();
    expect(screen.getByLabelText('担任からの所見')).toBeTruthy();
  });

  it('saves what was changed', async () => {
    m.save.mockResolvedValue(report());
    await open();
    fireEvent.change(screen.getByLabelText('算数 rating'), { target: { value: 'B' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(m.save).toHaveBeenCalledWith('r1', expect.objectContaining({ content: expect.objectContaining({ subjects: expect.objectContaining({ 算数: expect.objectContaining({ rating: 'B' }) }) }) })));
  });

  it('fills from school data and finalises', async () => {
    m.prefill.mockResolvedValue(report({ school_days: 71 }));
    m.save.mockResolvedValue(report());
    m.finalise.mockResolvedValue(report({ is_locked: true, finalised_by: '佐藤 花' }));
    await open();
    fireEvent.click(screen.getByText('Fill from school data'));
    await waitFor(() => expect(m.prefill).toHaveBeenCalledWith('r1'));
    fireEvent.click(screen.getByText('Finalise'));
    await waitFor(() => expect(m.finalise).toHaveBeenCalledWith('r1'));
    expect(await screen.findByText(/It cannot be changed unless an administrator re-opens it/)).toBeTruthy();
    expect(screen.queryByText('Save')).toBeNull();
  });

  it('a finalised report is read-only and only an administrator can re-open it', async () => {
    await open(report({ is_locked: true, finalised_by: '佐藤 花' }));
    expect(screen.getByLabelText('国語 rating')).toHaveProperty('disabled', true);
    expect(screen.queryByText('Re-open…')).toBeNull();
    cleanup();
    role.current = 'admin';
    m.reopen.mockResolvedValue(report());
    await open(report({ is_locked: true, finalised_by: '佐藤 花' }));
    fireEvent.click(screen.getByText('Re-open…'));
    const go = screen.getByText('Re-open report');
    expect(go).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByPlaceholderText('Why is it being re-opened?'), { target: { value: '訂正' } });
    fireEvent.click(go);
    await waitFor(() => expect(m.reopen).toHaveBeenCalledWith('r1', '訂正'));
  });
});

describe('Term report print', () => {
  it('prints the layout: school, student, ratings, behaviour, attendance and comments', () => {
    const { container } = render(<TermReportPrint rep={report()} />);
    const text = container.textContent || '';
    for (const part of ['通知表', '若葉学園', '2026年度 1学期', '山田 太郎', '国語', '知識・技能', '責任感', '授業日数', '担任からの所見', 'よくがんばりました。', '鈴木 一郎', '佐藤 花']) expect(text).toContain(part);
    expect(container.querySelectorAll('tbody tr').length).toBeGreaterThan(4);
  });

  it('leaves out the parts the layout switches off', () => {
    const rep = report({ layout: { ...config, viewpoints: false, sections: { attendance: false, conduct: false, comments: false } } });
    const text = render(<TermReportPrint rep={rep} />).container.textContent || '';
    expect(text).not.toContain('知識・技能');
    expect(text).not.toContain('行動の記録');
    expect(text).not.toContain('出欠の記録');
    expect(text).not.toContain('担任からの所見');
  });
});
