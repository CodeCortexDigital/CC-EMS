// The Japanese cumulative record (指導要録): open a student's record, fill it in year by year, put the two seals (印) on a year, export it.
// Server side: backend/services/education/records/ (URLs under /auth/records/). The form itself (subjects, years, scales) comes from the
// server in `definition`, so a screen never hard-codes what the reference form contains.
import api from './api';

const base = '/auth/records';

export type Level = 'elementary' | 'junior_high' | 'high';
export const LEVEL_LABEL: Record<Level, string> = { elementary: '小学校', junior_high: '中学校', high: '高等学校' };

export interface Viewpoint { key: 'v1' | 'v2' | 'v3'; label: string }
export interface SubjectDef { code: string; name: string; grades: number[]; rating_grades: number[] }
export interface FormDefinition {
  level: Level; label: string; person: string; grades: number; rating_max: number;
  subjects: SubjectDef[]; viewpoints: Viewpoint[]; behaviour_items: Array<{ key: string; label: string }>;
  special_activities: Array<{ key: string; label: string }>; high_subject_areas: string[];
  foreign_activity_grades: number[]; integrated_grades: number[]; moral_grades: number[]; text_limits: Record<string, number>;
}

export interface SubjectCell { v1?: string; v2?: string; v3?: string; rating?: number }
export interface Course { area: string; course: string; v1?: string; v2?: string; v3?: string; rating?: number; credits?: number }
export interface YearContent {
  subjects?: Record<string, SubjectCell>; courses?: Course[];
  moral?: string; comment?: string; integrated_activity?: string; integrated_viewpoint?: string; integrated_evaluation?: string;
  foreign_v1?: string; foreign_v2?: string; foreign_v3?: string;
  special_activities?: Record<string, boolean>; behaviour?: Record<string, boolean>;
}
export interface RecordYear {
  id: string; grade: number; year_label: string; class_name: string; roll_number: string; teacher_name: string; principal_name: string;
  school_days: number | null; suspended_days: number | null; abroad_days: number | null; absent_days: number | null;
  required_days: number | null; present_days: number | null; attendance_remarks: string; content: YearContent; locked: boolean;
  teacher_confirmed_at: string | null; teacher_confirmed_by: string; principal_confirmed_at: string | null; principal_confirmed_by: string;
}
export interface CreditTotals { courses: Array<{ area: string; course: string; credits: number }>; total: number }
export interface CumulativeRecord {
  id: string; student: string; student_number: string; student_name: string; gender: string; date_of_birth: string | null; class_name: string;
  level: Level; student_furigana: string; student_address: string; guardian_name: string; guardian_furigana: string; guardian_address: string;
  previous_history: string; entry_date: string | null; entry_kind: 'enrolled' | 'admitted'; entry_grade: number;
  transfer_in_date: string | null; transfer_in_grade: number | null; transfer_out_date: string | null; transfer_out_note: string;
  abroad_from: string | null; abroad_to: string | null; graduation_date: string | null; next_school: string; next_work: string;
  school_name: string; school_address: string; course_name: string;
  years: RecordYear[]; definition: FormDefinition; credit_totals: CreditTotals | Record<string, never>;
}
export interface RosterRow {
  student: string; student_number: string; student_name: string; class_name: string; record_id: string | null; level: Level; years: number; years_sealed: number;
}
export type YearInput = Partial<Pick<RecordYear, 'year_label' | 'class_name' | 'roll_number' | 'teacher_name' | 'principal_name' | 'school_days' | 'suspended_days'
  | 'abroad_days' | 'absent_days' | 'attendance_remarks'>> & { content?: YearContent };

/** The message the server sent for a failed call (field errors are joined), else a fallback. */
export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d.detail === 'string') return d.detail;
  if (typeof d === 'object') {
    const msgs = Object.values(d).filter((v) => typeof v === 'string') as string[];
    if (msgs.length) return msgs.slice(0, 3).join(' ');
  }
  return fallback;
};

const records = {
  roster: async (params: { class?: string; search?: string } = {}) => (await api.get<{ count: number; results: RosterRow[] }>(`${base}/roster/`, { params })).data.results,
  open: async (student: string) => (await api.post<CumulativeRecord>(`${base}/open/`, { student })).data,
  get: async (id: string) => (await api.get<CumulativeRecord>(`${base}/${id}/`)).data,
  update: async (id: string, patch: Partial<CumulativeRecord>) => (await api.patch<CumulativeRecord>(`${base}/${id}/`, patch)).data,
  saveYear: async (id: string, grade: number, input: YearInput) => (await api.put<RecordYear>(`${base}/${id}/years/${grade}/`, input)).data,
  prefillYear: async (id: string, grade: number) => (await api.post<RecordYear>(`${base}/${id}/years/${grade}/prefill/`)).data,
  seal: async (id: string, grade: number, as: 'teacher' | 'principal') => (await api.post<RecordYear>(`${base}/${id}/years/${grade}/confirm/`, { as })).data,
  reopen: async (id: string, grade: number, reason: string) => (await api.post<RecordYear>(`${base}/${id}/years/${grade}/reopen/`, { reason })).data,
  /** Download the structured export (one row per student and year) as a CSV file. */
  downloadCsv: async (id: string | null, params: { class?: string; all?: boolean } = {}) => {
    const url = id ? `${base}/${id}/export/` : `${base}/export/`;
    const res = await api.get(url, { params: { type: 'csv', ...(params.class ? { class: params.class } : {}), ...(params.all ? { all: 1 } : {}) }, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a');
    a.href = href; a.download = id ? 'shido-yoroku.csv' : 'shido-yoroku-class.csv';
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
  },
};

export default records;
