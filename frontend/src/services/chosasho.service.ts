// The 調査書 (the junior-high report sent to a high school): preview from the 指導要録, issue to a named school, read an issued copy.
// Server side: backend/services/education/records/chosasho.py and chosasho_views.py (URLs under /auth/records/<id>/chosasho/).
import api from './api';

const base = '/auth/records';

export interface ChosashoMark { key: string; label: string; years: Record<'1' | '2' | '3', boolean> }
export interface Chosasho {
  student: { name: string; furigana: string; gender: string; date_of_birth: string | null; student_number: string; address: string };
  school: { name: string; address: string; principal: string };
  graduation: { date: string | null };
  subjects: Array<{ code: string; name: string; ratings: Record<'1' | '2' | '3', number | null> }>;
  totals: Record<'1' | '2' | '3', { sum: number; count: number; max: number }>;
  special_activities: ChosashoMark[]; behaviour: ChosashoMark[];
  comments: Record<'1' | '2' | '3', string>;
  attendance: Record<'1' | '2' | '3', { school_days: number | null; suspended_days: number | null; absent_days: number | null; remarks: string } | null>;
  prepared_on: string; problems: string[]; ready: boolean;
}
export interface ChosashoIssue { id: string; issued_to: string; note: string; issued_at: string; issued_by: string; snapshot?: Chosasho }

const chosasho = {
  get: async (recordId: string) => (await api.get<{ chosasho: Chosasho; issues: ChosashoIssue[] }>(`${base}/${recordId}/chosasho/`)).data,
  issue: async (recordId: string, issued_to: string, note: string) => (await api.post<ChosashoIssue>(`${base}/${recordId}/chosasho/`, { issued_to, note })).data,
  issued: async (recordId: string, issueId: string) => (await api.get<ChosashoIssue>(`${base}/${recordId}/chosasho/${issueId}/`)).data,
};

export default chosasho;
