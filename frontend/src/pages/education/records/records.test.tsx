// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const role = vi.hoisted(() => ({ current: 'teacher' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: role.current }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/class.service', () => ({
  default: { getAll: vi.fn().mockResolvedValue({ data: [{ id: 'c1', name: 'Grade 2' }] }) },
}));
vi.mock('@/services/records.service', async (orig) => {
  const actual = await orig<typeof import('@/services/records.service')>();
  return {
    ...actual,
    default: { roster: vi.fn(), open: vi.fn(), get: vi.fn(), update: vi.fn(), saveYear: vi.fn(), prefillYear: vi.fn(), seal: vi.fn(), reopen: vi.fn(), downloadCsv: vi.fn() },
  };
});

import records, { CumulativeRecord, RecordYear } from '@/services/records.service';
import RecordsPage from './RecordsPage';
import RecordEditorPage from './RecordEditorPage';

const m = records as unknown as Record<string, ReturnType<typeof vi.fn>>;

const definition = {
  level: 'elementary', label: '小学校児童指導要録', person: '児童', grades: 6, rating_max: 3,
  subjects: [
    { code: 'seikatsu', name: '生活', grades: [1, 2], rating_grades: [] },
    { code: 'rika', name: '理科', grades: [3, 4, 5, 6], rating_grades: [3, 4, 5, 6] },
    { code: 'kokugo', name: '国語', grades: [1, 2, 3, 4, 5, 6], rating_grades: [3, 4, 5, 6] },
  ],
  viewpoints: [{ key: 'v1', label: '知識・技能' }, { key: 'v2', label: '思考・判断・表現' }, { key: 'v3', label: '主体的に学習に取り組む態度' }],
  behaviour_items: [{ key: 'basic', label: '基本的な生活習慣' }], special_activities: [{ key: 'class', label: '学級活動' }],
  high_subject_areas: [], foreign_activity_grades: [3, 4], integrated_grades: [3, 4, 5, 6], moral_grades: [1, 2, 3, 4, 5, 6], text_limits: {},
};

const year = (over: Partial<RecordYear> = {}): RecordYear => ({
  id: 'y1', grade: 2, year_label: '2026', class_name: '2-1', roll_number: '3', teacher_name: 'Ms Sato', principal_name: 'Mr Ito',
  school_days: 200, suspended_days: 0, abroad_days: null, absent_days: 2, required_days: 200, present_days: 198, attendance_remarks: '',
  content: {}, locked: false, teacher_confirmed_at: null, teacher_confirmed_by: '', principal_confirmed_at: null, principal_confirmed_by: '', ...over,
});

const record = (years: RecordYear[] = []): CumulativeRecord => ({
  id: 'r1', student: 's1', student_number: 'S-001', student_name: 'Aoi Tanaka', gender: 'F', date_of_birth: '2018-04-02', class_name: 'Grade 2',
  level: 'elementary', student_furigana: '', student_address: '', guardian_name: '', guardian_furigana: '', guardian_address: '', previous_history: '',
  entry_date: null, entry_kind: 'enrolled', entry_grade: 1, transfer_in_date: null, transfer_in_grade: null, transfer_out_date: null, transfer_out_note: '',
  abroad_from: null, abroad_to: null, graduation_date: null, next_school: '', next_work: '', school_name: '', school_address: '', course_name: '',
  years, definition: definition as any, credit_totals: {},
});

const renderEditor = () => render(
  <MemoryRouter initialEntries={['/education/records/r1']}>
    <Routes><Route path="/education/records/:id" element={<RecordEditorPage />} /></Routes>
  </MemoryRouter>,
);

const openLearning = async () => {
  await screen.findByRole('heading', { name: 'Aoi Tanaka' });
  fireEvent.click(screen.getByRole('tab', { name: /Learning record/ }));
  fireEvent.click(screen.getByRole('button', { name: /^2年/ }));
};

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  role.current = 'teacher';
});

describe('RecordsPage', () => {
  it('lists students and opens a record', async () => {
    m.roster.mockResolvedValue([{ student: 's1', student_number: 'S-001', student_name: 'Aoi Tanaka', class_name: 'Grade 2A', record_id: null, level: 'elementary', years: 3, years_sealed: 1 }]);
    m.open.mockResolvedValue({ id: 'r9' });
    render(
      <MemoryRouter initialEntries={['/education/records']}>
        <Routes>
          <Route path="/education/records" element={<RecordsPage />} />
          <Route path="/education/records/:id" element={<p>editor r9</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText('Aoi Tanaka')).toBeTruthy();
    expect(screen.getByText('小学校')).toBeTruthy();
    expect(screen.getByText('3 / 1')).toBeTruthy();
    expect(screen.queryByText('Export all (CSV)')).toBeNull();
    fireEvent.click(screen.getByText('Open record'));
    await waitFor(() => expect(m.open).toHaveBeenCalledWith('s1'));
    expect(await screen.findByText('editor r9')).toBeTruthy();
  });

  it('shows the export-all button to administrators and an empty state', async () => {
    role.current = 'admin';
    m.roster.mockResolvedValue([]);
    render(<MemoryRouter><RecordsPage /></MemoryRouter>);
    expect(await screen.findByText('No students found.')).toBeTruthy();
    expect(screen.getByText('Export all (CSV)')).toBeTruthy();
  });
});

describe('RecordEditorPage', () => {
  it('shows only the subjects of the chosen year and hides 評定 where there is none', async () => {
    m.get.mockResolvedValue(record([year()]));
    renderEditor();
    await openLearning();
    expect(screen.getByText('生活')).toBeTruthy();
    expect(screen.queryByText('理科')).toBeNull();
    expect(screen.getByText('国語')).toBeTruthy();
    // year 2: no rating for 国語 or 生活
    expect(screen.queryByLabelText('国語 評定')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /^3年/ }));
    expect(screen.getByText('理科')).toBeTruthy();
    expect(screen.getByLabelText('国語 評定')).toBeTruthy();
    expect(screen.getByLabelText('総合的な学習の時間: 学習活動')).toBeTruthy();
  });

  it('saves the year with the edited marks', async () => {
    m.get.mockResolvedValue(record([year()]));
    m.saveYear.mockResolvedValue(year({ content: { subjects: { kokugo: { v1: 'A' } } } }));
    renderEditor();
    await openLearning();
    fireEvent.change(screen.getByLabelText('国語 知識・技能'), { target: { value: 'A' } });
    fireEvent.click(screen.getByText('Save year'));
    await waitFor(() => expect(m.saveYear).toHaveBeenCalledTimes(1));
    const [id, grade, body] = m.saveYear.mock.calls[0];
    expect(id).toBe('r1');
    expect(grade).toBe(2);
    expect(body.teacher_name).toBe('Ms Sato');
    expect(body.content.subjects.kokugo.v1).toBe('A');
  });

  it('shows the locked banner and disables inputs on a sealed year', async () => {
    m.get.mockResolvedValue(record([year({ locked: true, principal_confirmed_at: '2027-03-20T00:00:00Z', principal_confirmed_by: 'Mr Ito' })]));
    renderEditor();
    await openLearning();
    expect(screen.getByText('Locked: the principal has sealed this year')).toBeTruthy();
    expect((screen.getByLabelText('国語 知識・技能') as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByText('Save year') as HTMLButtonElement).disabled).toBe(true);
  });

  it('offers the principal seal and re-open only to administrators', async () => {
    m.get.mockResolvedValue(record([year({ teacher_confirmed_at: '2027-03-01T00:00:00Z', teacher_confirmed_by: 'Ms Sato' })]));
    renderEditor();
    await openLearning();
    fireEvent.click(screen.getByRole('tab', { name: /Attendance & seals/ }));
    expect(screen.getByText('Seal as class teacher')).toBeTruthy();
    expect(screen.queryByText('Seal as principal')).toBeNull();
    expect(screen.getByTestId('present').textContent).toBe('198');
    cleanup();

    role.current = 'admin';
    m.get.mockResolvedValue(record([year({ teacher_confirmed_at: '2027-03-01T00:00:00Z', teacher_confirmed_by: 'Ms Sato' })]));
    m.seal.mockResolvedValue(year({ locked: true }));
    renderEditor();
    await openLearning();
    fireEvent.click(screen.getByRole('tab', { name: /Attendance & seals/ }));
    fireEvent.click(screen.getByText('Seal as principal'));
    await waitFor(() => expect(m.seal).toHaveBeenCalledWith('r1', 2, 'principal'));
    expect(await screen.findByText('Re-open…')).toBeTruthy();
  });
});
