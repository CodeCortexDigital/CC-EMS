// MEXT education data standards: the school's MEXT school code, and the IDs other systems use for students and teachers.
// Server side: backend/services/education/records/standards_views.py (URLs under /auth/records/).
import api from './api';

const base = '/auth/records';

export interface ExternalIdRow { id: string; kind: 'student' | 'teacher'; local_id: string; name: string; system: string; external_id: string }
export interface ExternalIdList { results: ExternalIdRow[]; systems: string[]; saved?: number; errors?: Array<{ row: number; message: string }> }

export interface RosterPreview {
  files: Record<string, number>; skipped: { students_without_class: number; teachers_inactive: number }; left_out: string[]; contacts_included: boolean; school_code: string;
}

export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  return (d && (d.school_code || d.system || d.rows || d.detail)) || fallback;
};

const standards = {
  get: async () => (await api.get<{ school_code: string; systems: string[] }>(`${base}/standards/`)).data,
  saveSchoolCode: async (school_code: string) => (await api.put<{ school_code: string }>(`${base}/standards/`, { school_code })).data,
  ids: async (system?: string) => (await api.get<ExternalIdList>(`${base}/external-ids/`, { params: system ? { system } : {} })).data,
  importCsv: async (system: string, csv: string) => (await api.post<ExternalIdList>(`${base}/external-ids/`, { system, csv })).data,
  remove: async (id: string, system?: string) => (await api.delete<ExternalIdList>(`${base}/external-ids/`, { params: { id, ...(system ? { system } : {}) } })).data,
  rosterPreview: async (contacts: boolean) => (await api.get<RosterPreview>(`${base}/oneroster/`, { params: { preview: 1, ...(contacts ? { contacts: 1 } : {}) } })).data,
  downloadRoster: async (contacts: boolean) => {
    const res = await api.get(`${base}/oneroster/`, { params: contacts ? { contacts: 1 } : {}, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = 'oneroster.zip'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
  },
  exportCsv: async (system?: string) => {
    const res = await api.get(`${base}/external-ids/`, { params: { export: 'csv', ...(system ? { system } : {}) }, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = 'external-ids.csv'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
  },
};

export default standards;
