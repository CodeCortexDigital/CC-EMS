// The intervention queue: tasks about named students, opened by staff, by the attendance ladder and by the early-warning scan.
import api, { extractListData } from './api';

const base = '/auth/interventions';

export type Status = 'open' | 'in_progress' | 'done' | 'dismissed';
export type Source = 'absence' | 'risk' | 'behaviour' | 'manual';
export const SOURCE_LABEL: Record<Source, string> = { absence: 'Attendance', risk: 'Early warning', behaviour: 'Behaviour', manual: 'Added by staff' };
export const STATUS_LABEL: Record<Status, string> = { open: 'Open', in_progress: 'In progress', done: 'Done', dismissed: 'Dismissed' };

export type Outcome = 'improved' | 'no_change' | 'worse' | 'not_measured';
export const OUTCOME_LABEL: Record<Outcome, string> = { improved: 'Improved', no_change: 'No change', worse: 'Got worse', not_measured: 'Not measured yet' };

export interface Note { id: string; author_name: string; text: string; created_at: string }
export interface Intervention {
  id: string; student: string; student_name: string; student_number: string; class_name: string; source: Source; title: string;
  description: string; suggested_actions: string[]; status: Status; priority: 'normal' | 'high'; owner: string | null; owner_name: string;
  due_date: string | null; is_overdue: boolean; notes: Note[]; created_at: string; closed_at: string | null; closure_note: string;
  started_on: string | null; sessions_delivered: number; outcome: Outcome | ''; evidence: string; review_on: string | null; is_review_due: boolean;
}
export interface Reach {
  raised: number; students_flagged: number; students_reached: number; sessions_delivered: number; average_days_to_start: number | null;
  closed: number; results: Record<Outcome, number>; closed_without_result: number; reviews_due: number;
}
export interface Summary { open: number; in_progress: number; overdue: number; unassigned: number; mine: number; high_priority: number }
export interface Owner { id: string; name: string; role: string }
export interface Filters { status?: string; source?: string; owner?: string; overdue?: boolean; active?: boolean; search?: string }
export interface NewIntervention { student: string; title: string; description?: string; priority?: 'normal' | 'high'; owner?: string | null; due_date?: string | null }

const interventions = {
  async list(f: Filters = {}): Promise<Intervention[]> {
    const params: Record<string, string> = {};
    if (f.status) params.status = f.status;
    if (f.source) params.source = f.source;
    if (f.owner) params.owner = f.owner;
    if (f.overdue) params.overdue = '1';
    if (f.active) params.active = '1';
    if (f.search) params.search = f.search;
    return extractListData<Intervention>((await api.get(`${base}/`, { params })).data);
  },
  async get(id: string): Promise<Intervention> { return (await api.get(`${base}/${id}/`)).data; },
  async summary(): Promise<Summary> { return (await api.get(`${base}/summary/`)).data; },
  async owners(): Promise<Owner[]> { return (await api.get(`${base}/owners/`)).data; },
  async create(body: NewIntervention): Promise<Intervention> { return (await api.post(`${base}/`, body)).data; },
  async update(id: string, body: Partial<Pick<Intervention, 'title' | 'description' | 'priority' | 'owner' | 'due_date' | 'started_on' | 'review_on' | 'outcome' | 'evidence'>>): Promise<Intervention> {
    return (await api.patch(`${base}/${id}/`, body)).data;
  },
  async addNote(id: string, text: string): Promise<Note> { return (await api.post(`${base}/${id}/add_note/`, { text })).data; },
  async start(id: string): Promise<Intervention> { return (await api.post(`${base}/${id}/start/`)).data; },
  async logSession(id: string): Promise<Intervention> { return (await api.post(`${base}/${id}/log_session/`)).data; },
  async reach(): Promise<Reach> { return (await api.get(`${base}/reach/`)).data; },
  async complete(id: string, note: string, result: { outcome?: Outcome; evidence?: string } = {}): Promise<Intervention> {
    return (await api.post(`${base}/${id}/complete/`, { note, ...result })).data;
  },
  async dismiss(id: string, note: string): Promise<Intervention> { return (await api.post(`${base}/${id}/dismiss/`, { note })).data; },
  async reopen(id: string): Promise<Intervention> { return (await api.post(`${base}/${id}/reopen/`)).data; },
};

export default interventions;
