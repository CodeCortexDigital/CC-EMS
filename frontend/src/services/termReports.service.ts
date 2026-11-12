// The Japanese term report (通知表): the school's layout, and a student's report for a term. Server side: backend/services/education/records/
// (termreport.py and termreport_views.py, URLs under /auth/records/). The layout is data a school edits, so no screen hard-codes the subjects.
import api from './api';

const base = '/auth/records';

export type Scale = 'abc' | 'five' | 'percent';
export interface CommentField { key: string; label: string }
export interface LayoutConfig {
  title: string; scale: Scale; viewpoints: boolean; subjects: string[]; conduct_items: string[]; comment_fields: CommentField[];
  sections: { attendance: boolean; conduct: boolean; comments: boolean }; thresholds: { abc: number[]; five: number[] };
}
export interface Layout { id: string; name: string; level: 'elementary' | 'junior_high' | 'high'; is_default: boolean; config: LayoutConfig }
export interface LayoutList { layouts: Layout[]; scales: Record<Scale, string>; viewpoints: Array<{ key: 'v1' | 'v2' | 'v3'; label: string }> }

export interface SubjectCell { v1?: string; v2?: string; v3?: string; rating?: string }
export interface ReportContent { subjects: Record<string, SubjectCell>; conduct: Record<string, boolean>; comments: Record<string, string> }
export interface TermReport {
  id: string; student: string; student_name: string; student_number: string; layout: LayoutConfig; term: string | null; year_label: string; term_label: string;
  class_name: string; teacher_name: string; principal_name: string; school_days: number | null; suspended_days: number | null; absent_days: number | null;
  attendance_remarks: string; content: ReportContent; is_locked: boolean; finalised_at: string | null; finalised_by: string; school_name: string;
}
export interface TermRoster { year: string; terms: Array<{ id: string; name: string }>; results: Array<{ student: string; student_number: string; student_name: string; report_id: string | null; is_locked: boolean }> }
export type ReportInput = Partial<Pick<TermReport, 'class_name' | 'teacher_name' | 'principal_name' | 'attendance_remarks' | 'school_days' | 'suspended_days' | 'absent_days'>> & { content?: ReportContent };

export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d === 'string') return d;
  return d.detail || (Object.values(d).filter((v) => typeof v === 'string')[0] as string) || fallback;
};

const termReports = {
  layouts: async () => (await api.get<LayoutList>(`${base}/term-layouts/`)).data,
  saveLayout: async (l: Partial<Layout> & { config: LayoutConfig }) => (await api.post<Layout>(`${base}/term-layouts/`, l)).data,
  roster: async (params: { class?: string; term?: string }) => (await api.get<TermRoster>(`${base}/term/roster/`, { params })).data,
  open: async (student: string, term: string) => (await api.post<TermReport>(`${base}/term/open/`, { student, term })).data,
  get: async (id: string) => (await api.get<TermReport>(`${base}/term/${id}/`)).data,
  save: async (id: string, input: ReportInput) => (await api.put<TermReport>(`${base}/term/${id}/`, input)).data,
  prefill: async (id: string) => (await api.post<TermReport>(`${base}/term/${id}/prefill/`)).data,
  finalise: async (id: string) => (await api.post<TermReport>(`${base}/term/${id}/finalise/`)).data,
  reopen: async (id: string, reason: string) => (await api.post<TermReport>(`${base}/term/${id}/reopen/`, { reason })).data,
};

export default termReports;
