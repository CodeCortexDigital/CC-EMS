// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import RecordPrint from './RecordPrint';
import type { CumulativeRecord, FormDefinition, RecordYear } from '@/services/records.service';

afterEach(cleanup);

const viewpoints = [{ key: 'v1' as const, label: '知識・技能' }, { key: 'v2' as const, label: '思考・判断・表現' }, { key: 'v3' as const, label: '主体的に学習に取り組む態度' }];
const behaviour = [['basic_habits', '基本的な生活習慣'], ['health_fitness', '健康・体力の向上'], ['kindness', '思いやり・協力'], ['responsibility', '責任感']]
  .map(([key, label]) => ({ key, label }));

const elementary: FormDefinition = {
  level: 'elementary', label: '小学校児童指導要録', person: '児童', grades: 6, rating_max: 3, viewpoints, behaviour_items: behaviour,
  subjects: [
    { code: 'JPN', name: '国語', grades: [1, 2, 3, 4, 5, 6], rating_grades: [3, 4, 5, 6] }, { code: 'LIFE', name: '生活', grades: [1, 2], rating_grades: [] },
    { code: 'SCI', name: '理科', grades: [3, 4, 5, 6], rating_grades: [3, 4, 5, 6] },
  ],
  special_activities: [{ key: 'class_activity', label: '学級活動' }, { key: 'council', label: '児童会活動' }, { key: 'club', label: 'クラブ活動' }, { key: 'school_event', label: '学校行事' }],
  high_subject_areas: [], foreign_activity_grades: [3, 4], integrated_grades: [3, 4, 5, 6], moral_grades: [1, 2, 3, 4, 5, 6], text_limits: {},
};

const year = (grade: number, over: Partial<RecordYear> = {}): RecordYear => ({
  id: `y${grade}`, grade, year_label: '令和8年度', class_name: '6年1組', roll_number: '12', teacher_name: '佐藤 花', principal_name: '田中 校長',
  school_days: 200, suspended_days: 2, abroad_days: null, absent_days: 3, required_days: 198, present_days: 195, attendance_remarks: '', content: {}, locked: false,
  teacher_confirmed_at: null, teacher_confirmed_by: '', principal_confirmed_at: null, principal_confirmed_by: '', ...over,
});

const record = (over: Partial<CumulativeRecord> = {}): CumulativeRecord => ({
  id: 'r1', student: 's1', student_number: 'WK26-001', student_name: '山田 太郎', gender: 'male', date_of_birth: '2014-05-02', class_name: '6年',
  level: 'elementary', student_furigana: 'やまだ たろう', student_address: 'みどり市 緑町 1-2-3', guardian_name: '山田 一郎', guardian_furigana: 'やまだ いちろう',
  guardian_address: 'みどり市 緑町 1-2-3', previous_history: 'みどり幼稚園', entry_date: '2020-04-06', entry_kind: 'enrolled', entry_grade: 1, transfer_in_date: null,
  transfer_in_grade: null, transfer_out_date: null, transfer_out_note: '', abroad_from: null, abroad_to: null, graduation_date: null, next_school: '', next_work: '',
  school_name: 'みどり市立 若葉学園', school_address: '福岡県 みどり市 緑町 1-2-3', course_name: '', years: [], definition: elementary, credit_totals: {}, ...over,
});

describe('printed cumulative record', () => {
  it('prints 様式1 with the pupil, guardian, era dates and the seals of a sealed year', () => {
    const sealed = year(6, { principal_confirmed_at: '2027-03-24T01:00:00Z', teacher_confirmed_at: '2027-03-20T01:00:00Z' });
    render(<RecordPrint rec={record({ years: [sealed] })} />);
    const page = screen.getAllByRole('heading', { level: 1 })[0].closest('section') as HTMLElement;
    expect(within(page).getByText('小学校児童指導要録（参考様式）')).toBeTruthy();
    expect(within(page).getByText('やまだ たろう')).toBeTruthy();
    expect(within(page).getByText('山田 太郎')).toBeTruthy();
    expect(page.textContent).toContain('令和2年4月6日　第1学年入学');
    expect(page.textContent).toContain('平成26年5月2日生');
    expect(within(page).getAllByText('印').length).toBe(2);       // class teacher and principal
    expect(within(page).getByText('みどり幼稚園')).toBeTruthy();
  });

  it('shows ratings only in the cells the form has, and draws the rest as crossed out', () => {
    const y3 = year(3, { content: { subjects: { JPN: { v1: 'A', v2: 'B', v3: 'C', rating: 2 } }, behaviour: { kindness: true }, special_activities: { club: true }, comment: '落ち着いて学習できた' } });
    const { container } = render(<RecordPrint rec={record({ years: [year(1), y3] })} />);
    expect(container.querySelectorAll('td.na').length).toBeGreaterThan(10);            // 生活 from year 3, 理科 before year 3, no 評定 before year 3
    const text = container.textContent ?? '';
    expect(text).toContain('各 教 科 の 学 習 の 記 録');
    expect(text).toContain('落ち着いて学習できた');
    const kind = Array.from(container.querySelectorAll('tr')).find((tr) => tr.textContent?.includes('思いやり・協力'));
    expect(kind?.textContent).toContain('○');
  });

  it('prints the attendance record with the days worked out by the server', () => {
    const { container } = render(<RecordPrint rec={record({ years: [year(6)] })} />);
    const row = Array.from(container.querySelectorAll('tr')).find((tr) => tr.textContent?.startsWith('6200'));
    expect(row?.textContent).toContain('200');
    expect(row?.textContent).toContain('198');
    expect(row?.textContent).toContain('195');
  });

  it('prints a high school record with credits, a credit table on the back of 様式1, and no behaviour table', () => {
    const high: FormDefinition = { ...elementary, level: 'high', label: '高等学校生徒指導要録', person: '生徒', grades: 4, rating_max: 5, subjects: [], high_subject_areas: ['国語'],
      foreign_activity_grades: [], moral_grades: [], integrated_grades: [1, 2, 3, 4], special_activities: [{ key: 'homeroom', label: 'ホームルーム活動' }, { key: 'council', label: '生徒会活動' }, { key: 'school_event', label: '学校行事' }] };
    const y1 = year(1, { content: { courses: [{ area: '国語', course: '現代の国語', v1: 'A', v2: 'B', v3: 'A', rating: 4, credits: 2 }] } });
    const { container } = render(<RecordPrint rec={record({ level: 'high', definition: high, years: [y1], credit_totals: { courses: [{ area: '国語', course: '現代の国語', credits: 2 }], total: 2 } })} />);
    const text = container.textContent ?? '';
    expect(text).toContain('高等学校（全日制の課程・定時制の課程）生徒指導要録');
    expect(text).toContain('各教科・科目等の修得単位数の記録');
    expect(text).toContain('現代の国語');
    expect(text).toContain('ABA');
    expect(text).not.toContain('行 動 の 記 録');
    expect(text).toContain('留学中の授業日数');
  });
});
