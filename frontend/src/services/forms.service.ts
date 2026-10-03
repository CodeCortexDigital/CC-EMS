// Permission slips and e-signature forms: the school builds and tracks them, parents read and sign them.
import api, { extractListData } from './api';

const base = '/auth/forms';

export type QuestionType = 'yes_no' | 'text' | 'choice';
export interface Question { id: string; label: string; type: QuestionType; options: string[]; required: boolean }

export interface FormTemplate {
  id: string; title: string; body: string; questions: Question[]; audience: 'everyone' | 'classes'; classes: string[];
  due_date: string | null; status: 'draft' | 'published' | 'archived'; version: number; published_at: string | null;
  counts: { total: number; signed: number; declined: number; pending: number };
}
export type TemplateInput = Partial<Pick<FormTemplate, 'title' | 'body' | 'questions' | 'audience' | 'classes' | 'due_date'>>;

export interface TrackerRow {
  id: string; student: string; student_name: string; class_name: string; status: 'pending' | 'signed' | 'declined';
  last_reminded_at: string | null; signed_at: string | null; signer_name: string;
}
export interface Tracker { template: string; due_date: string | null; counts: FormTemplate['counts']; rows: TrackerRow[] }

export interface MyForm {
  id: string; template: string; title: string; student: string; student_name: string; class_name: string;
  status: 'pending' | 'signed' | 'declined'; due_date: string | null; signed_at: string | null; signer_name: string;
  body?: string; questions?: Question[]; answers?: Record<string, string | boolean>;
}
export interface SignInput { signer_name: string; agree: boolean; decision: 'signed' | 'declined'; answers: Record<string, string | boolean> }

const forms = {
  async list(): Promise<FormTemplate[]> { return extractListData<FormTemplate>((await api.get(`${base}/templates/`)).data); },
  async create(body: TemplateInput): Promise<FormTemplate> { return (await api.post(`${base}/templates/`, body)).data; },
  async update(id: string, body: TemplateInput): Promise<FormTemplate> { return (await api.patch(`${base}/templates/${id}/`, body)).data; },
  async publish(id: string): Promise<FormTemplate> { return (await api.post(`${base}/templates/${id}/publish/`)).data; },
  async newVersion(id: string): Promise<FormTemplate> { return (await api.post(`${base}/templates/${id}/new_version/`)).data; },
  async archive(id: string): Promise<FormTemplate> { return (await api.post(`${base}/templates/${id}/archive/`)).data; },
  async tracker(id: string, status?: string): Promise<Tracker> { return (await api.get(`${base}/templates/${id}/tracker/`, { params: status ? { status } : {} })).data; },
  async remind(id: string): Promise<{ reminded: number; parents_told: number }> { return (await api.post(`${base}/templates/${id}/remind/`)).data; },
  /** The tracker as a CSV file the browser can save. */
  async exportCsv(id: string): Promise<Blob> { return (await api.get(`${base}/templates/${id}/export/`, { responseType: 'blob' })).data; },
  async classes(): Promise<Array<{ id: string; name: string }>> {
    return extractListData<{ id: string; name: string }>((await api.get('/auth/academics/classes/')).data).map((c) => ({ id: c.id, name: c.name }));
  },

  async mine(): Promise<MyForm[]> { return extractListData<MyForm>((await api.get(`${base}/my/`)).data); },
  async mineOne(id: string): Promise<MyForm> { return (await api.get(`${base}/my/${id}/`)).data; },
  async sign(id: string, body: SignInput): Promise<MyForm> { return (await api.post(`${base}/my/${id}/sign/`, body)).data; },
};

export default forms;
