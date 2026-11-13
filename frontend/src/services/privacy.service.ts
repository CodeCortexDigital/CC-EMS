// Privacy documents, consent, privacy requests and incidents (P14).
import api from './api';

export interface LegalDocsReply { documents: LegalDoc[]; template: { title: string; body: string }; history: LegalDoc[]; register_newer?: boolean }
export interface LegalDoc { id?: string; kind: string; kind_label?: string; version: number; title: string; body?: string; summary_of_changes?: string; published_at: string | null; school?: string | null; accepted?: number; people?: number }
export interface ConsentAnswer { granted: boolean; when: string; by: string; outdated: boolean }
export interface ConsentItem { type_id: string; key: string; label: string; description: string; current: ConsentAnswer | null; history: ConsentAnswer[] }
export interface PrivacyReq {
  id: string; kind: string; kind_label: string; details: string; status: string; status_label: string; student: string | null;
  requester: string; created_at: string; due_date: string; overdue: boolean; response: string; handled_by: string; closed_at: string | null;
  /** The student's ID, and what the office may do with this request. */
  student_ref?: string | null; can_export?: boolean; can_erase?: boolean;
}
export interface ErasePreview {
  student: { student_id: string; name: string }; already_erased: boolean; becomes: string;
  removed: Record<string, number>; kept_without_a_name: Record<string, number>; also: string[];
}
export interface ConsentTypeRow { id: string; key: string; label: string; description: string; subject: 'student' | 'user'; subject_label: string; is_active: boolean; version: number }
export interface SubProcessorRow { id?: number; name: string; purpose: string; data: string; location: string; optional: boolean; website: string }
export interface IncidentRow {
  id: string; reference: string; title: string; severity: string; status: string; status_label: string; discovered_at: string;
  regulator_deadline: string; regulator_overdue: boolean; schools: string[]; reported_by: string; personal_data: boolean;
  regulator_notified_at: string | null; schools_notified_at: string | null; people_notified_at: string | null;
  description?: string; data_affected?: string; people_affected?: number | null; school_ids?: string[];
  checklist?: { key: string; label: string; done_at: string | null }[]; updates?: { note: string; by: string; when: string }[];
}

export interface DataRegisterEntry {
  id: string; key: string; name: string; data_items: string; purpose: string; how_collected: string; retention: string; shared_with: string;
  storage_location: string; sensitive: boolean; needs_consent: boolean; is_active: boolean; reviewed_at: string; updated_by: string;
}
type RegisterReply = { entries: DataRegisterEntry[]; school: string };

export interface NoticeDraft { title: string; body: string; entries: number; sensitive: number; consent: { needed: boolean; exists: boolean; label: string } }
export interface NoticeDeliveryRow { user_id: string; name: string; email: string; role: string; children: string; read: boolean; read_at: string | null }
export interface NoticeDeliveryData { document: { title: string; version: number; published_at: string } | null; rows: NoticeDeliveryRow[]; summary: { people: number; read: number; not_read: number } }

export const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;

const privacyService = {
  legal: (kind: string) => api.get(`/privacy/legal/${kind}/`).then((r) => r.data),
  schoolNotice: (code: string) => api.get(`/privacy/legal/school/${code}/`).then((r) => r.data.document as LegalDoc),
  pending: () => api.get('/privacy/pending/').then((r) => r.data.documents as LegalDoc[]),
  accept: (ids: string[]) => api.post('/privacy/accept/', { documents: ids }).then((r) => r.data),
  me: () => api.get('/privacy/me/').then((r) => r.data as { mine: ConsentItem[]; children: { id: string; name: string; consents: ConsentItem[] }[]; requests: PrivacyReq[]; kinds: Record<string, string>; school_notice: LegalDoc | null; school_code?: string }),
  consent: (type: string, granted: boolean, student?: string) => api.post('/privacy/consent/', { type, granted, student }).then((r) => r.data),
  request: (kind: string, details: string, student?: string) => api.post('/privacy/requests/new/', { kind, details, student }).then((r) => r.data as { message: string }),
  photoConsent: (ids: string[]) => api.get('/privacy/photo-consent/', { params: { ids: ids.join(',') } }).then((r) => r.data.photo_consent as Record<string, boolean | null>),
  documents: () => api.get('/privacy/documents/').then((r) => r.data as LegalDocsReply),
  publishNotice: (title: string, body: string, summary: string) => api.post('/privacy/documents/', { title, body, summary }).then((r) => r.data),
  consentTypes: () => api.get('/privacy/consent-types/').then((r) => r.data.types as ConsentTypeRow[]),
  saveConsentType: (t: Partial<ConsentTypeRow>) => api.post('/privacy/consent-types/', t).then((r) => r.data.types as ConsentTypeRow[]),
  consentReport: (type?: string) => api.get('/privacy/consent-report/', { params: type ? { type } : {} }).then((r) => r.data),
  consentCsv: async (type: string) => {
    const res = await api.get('/privacy/consent-report/', { params: { type, export: 'csv' }, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = 'consent.csv'; a.click(); URL.revokeObjectURL(href);
  },
  noticeDraft: (lang: string) => api.get('/privacy/notice-draft/', { params: { lang } }).then((r) => r.data as NoticeDraft),
  ensureSensitiveConsent: (lang: string) => api.post('/privacy/notice-draft/', { ensure_consent: true, lang }).then((r) => r.data as { created: boolean; consent: { id: string; label: string } }),
  noticeDelivery: (who: 'parents' | 'staff' | 'all') => api.get('/privacy/notice-delivery/', { params: { who } }).then((r) => r.data as NoticeDeliveryData),
  noticeDeliveryCsv: async (who: 'parents' | 'staff' | 'all') => {
    const res = await api.get('/privacy/notice-delivery/', { params: { who, export: 'csv' }, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = 'notice-delivery.csv'; a.click(); URL.revokeObjectURL(href);
  },
  register: () => api.get('/privacy/register/').then((r) => r.data as RegisterReply),
  loadRegisterDefaults: (lang: string) => api.post('/privacy/register/', { action: 'load_defaults', lang }).then((r) => r.data as RegisterReply),
  saveRegisterEntry: (e: Partial<DataRegisterEntry>) => api.post('/privacy/register/', e).then((r) => r.data as RegisterReply),
  deleteRegisterEntry: (id: string) => api.delete('/privacy/register/', { params: { id } }).then((r) => r.data as RegisterReply),
  registerCsv: async () => {
    const res = await api.get('/privacy/register/', { params: { export: 'csv' }, responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = 'data-handling-register.csv'; a.click(); URL.revokeObjectURL(href);
  },
  requests: () => api.get('/privacy/requests/').then((r) => r.data as { results: PrivacyReq[]; statuses: Record<string, string> }),
  updateRequest: (id: string, body: { status?: string; response?: string }) => api.post(`/privacy/requests/${id}/`, body).then((r) => r.data.request as PrivacyReq),
  /** Download a copy of everything held about the student the request is about (a JSON file). */
  exportRequest: async (id: string, ref: string) => {
    const res = await api.get(`/privacy/requests/${id}/export/`, { responseType: 'blob' });
    const href = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a'); a.href = href; a.download = `student-data-${ref}.json`; a.click(); URL.revokeObjectURL(href);
  },
  /** What an erasure would do, without doing it. */
  erasePreview: (id: string) => api.post(`/privacy/requests/${id}/erase/`, {}).then((r) => r.data as { preview: ErasePreview; confirm_with: string }),
  /** Do it. `confirm` must be the student's ID. */
  erase: (id: string, confirm: string) => api.post(`/privacy/requests/${id}/erase/`, { confirm }).then((r) => r.data as { request: PrivacyReq; done: ErasePreview }),
  reportIncident: (title: string, description: string) => api.post('/privacy/incidents/report/', { title, description }).then((r) => r.data as { message: string }),
  platformDocuments: () => api.get('/privacy/platform/documents/').then((r) => r.data),
  publishPlatform: (kind: string, title: string, body: string, summary: string) => api.post('/privacy/platform/documents/', { kind, title, body, summary }).then((r) => r.data),
  subprocessors: () => api.get('/privacy/platform/subprocessors/').then((r) => r.data.subprocessors as SubProcessorRow[]),
  saveSubprocessor: (p: SubProcessorRow) => api.put('/privacy/platform/subprocessors/', p).then((r) => r.data.subprocessors as SubProcessorRow[]),
  deleteSubprocessor: (id: number) => api.delete('/privacy/platform/subprocessors/', { params: { id } }).then((r) => r.data.subprocessors as SubProcessorRow[]),
  incidents: () => api.get('/privacy/platform/incidents/').then((r) => r.data as { incidents: IncidentRow[]; statuses: Record<string, string>; severities: Record<string, string>; schools: { id: string; name: string }[] }),
  newIncident: (title: string, description: string, severity: string) => api.post('/privacy/platform/incidents/', { title, description, severity }).then((r) => r.data.incident as IncidentRow),
  incident: (id: string) => api.get(`/privacy/platform/incidents/${id}/`).then((r) => r.data.incident as IncidentRow),
  incidentAction: (id: string, body: Record<string, unknown>) => api.post(`/privacy/platform/incidents/${id}/`, body).then((r) => r.data.incident as IncidentRow),
};

export default privacyService;
