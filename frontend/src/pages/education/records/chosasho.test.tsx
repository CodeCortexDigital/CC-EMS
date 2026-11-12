// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const role = vi.hoisted(() => ({ current: 'admin' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: role.current }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/chosasho.service', () => ({ default: { get: vi.fn(), issue: vi.fn(), issued: vi.fn() } }));

import chosasho, { Chosasho } from '@/services/chosasho.service';
import ChosashoPage, { ChosashoPrint } from './ChosashoPage';

const m = chosasho as unknown as Record<string, ReturnType<typeof vi.fn>>;
const marks = (key: string, label: string, on = true) => ({ key, label, years: { '1': on, '2': on, '3': false } });
const data = (over: Partial<Chosasho> = {}): Chosasho => ({
  student: { name: '山田 太郎', furigana: 'やまだ たろう', gender: 'male', date_of_birth: '2011-05-01', student_number: 'W-001', address: '' },
  school: { name: 'みどり市立 若葉中学校', address: '', principal: '鈴木 一郎' }, graduation: { date: '2027-03-15' },
  subjects: [{ code: 'MATH', name: '数学', ratings: { '1': 5, '2': 4, '3': 5 } }, { code: 'JPN', name: '国語', ratings: { '1': 3, '2': null, '3': 4 } }],
  totals: { '1': { sum: 8, count: 2, max: 10 }, '2': { sum: 4, count: 1, max: 5 }, '3': { sum: 9, count: 2, max: 10 } },
  special_activities: [marks('class_activity', '学級活動')], behaviour: [marks('responsibility', '責任感')],
  comments: { '1': '一年の所見', '2': '', '3': '三年の所見' },
  attendance: { '1': { school_days: 200, suspended_days: 0, absent_days: 1, remarks: '' }, '2': null, '3': { school_days: 198, suspended_days: 1, absent_days: 0, remarks: '' } },
  prepared_on: '2026-11-12', problems: [], ready: true, ...over,
});

const open = (d: Chosasho, issues: any[] = []) => {
  m.get.mockResolvedValue({ chosasho: d, issues });
  render(<MemoryRouter initialEntries={['/education/records/r1/chosasho']}><Routes><Route path="/education/records/:id/chosasho" element={<ChosashoPage />} /></Routes></MemoryRouter>);
};

beforeEach(() => { vi.clearAllMocks(); cleanup(); role.current = 'admin'; });

describe('調査書 page', () => {
  it('prints the form: student, ratings with totals, marks, comments, attendance and the principal', async () => {
    open(data());
    await screen.findByText('調査書 (Report for high school admission)');
    const text = document.querySelector('.cs')!.textContent || '';
    for (const part of ['やまだ たろう', '山田 太郎', 'みどり市立 若葉中学校', '数学', '8 / 10', '学級活動', '責任感', '三年の所見', '授業日数', '鈴木 一郎', '上記のとおり']) expect(text).toContain(part);
  });

  it('lists what stops it being issued and will not issue', async () => {
    open(data({ ready: false, problems: ['第3学年に校長の印がありません。'] }));
    expect(await screen.findByText('第3学年に校長の印がありません。')).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('High school name'), { target: { value: '第一高校' } });
    expect(screen.getByText('Issue it')).toHaveProperty('disabled', true);
  });

  it('issues it to a named school and shows the kept copy', async () => {
    m.issue.mockResolvedValue({ id: 'i1', issued_to: '第一高校', note: '', issued_at: '2026-11-12T10:00:00Z', issued_by: '鈴木 一郎', snapshot: data() });
    open(data());
    const go = await screen.findByText('Issue it');
    expect(go).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByPlaceholderText('High school name'), { target: { value: '第一高校' } });
    fireEvent.click(go);
    await waitFor(() => expect(m.issue).toHaveBeenCalledWith('r1', '第一高校', ''));
    expect(await screen.findByText('Issued copy')).toBeTruthy();
    expect(document.querySelector('.cs')!.textContent).toContain('第一高校 御中');
  });

  it('only an administrator sees the issue form; the history opens the copy as it was issued', async () => {
    role.current = 'teacher';
    m.issued.mockResolvedValue({ id: 'i1', issued_to: '第一高校', note: '', issued_at: '2026-11-12T10:00:00Z', issued_by: '鈴木 一郎', snapshot: data({ comments: { '1': 'あのときの所見', '2': '', '3': '' } }) });
    open(data(), [{ id: 'i1', issued_to: '第一高校', note: '推薦', issued_at: '2026-11-12T10:00:00Z', issued_by: '鈴木 一郎' }]);
    await screen.findByText('Issued so far');
    expect(screen.queryByText('Issue it')).toBeNull();
    fireEvent.click(screen.getByText('View this copy'));
    await waitFor(() => expect(m.issued).toHaveBeenCalledWith('r1', 'i1'));
    expect(await screen.findByText('Issued copy')).toBeTruthy();
    expect(document.querySelector('.cs')!.textContent).toContain('あのときの所見');
  });

  it('the print component leaves unrecorded years blank', () => {
    const text = (render(<ChosashoPrint data={data()} />).container.textContent) || '';
    expect(text).toContain('調査書');
    expect(text).not.toContain('御中');
  });
});
