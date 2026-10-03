// Safety incident reports and their follow-up.
import api, { extractListData } from './api';

const base = '/auth/safety';

export const INCIDENT_TYPES: Array<[string, string]> = [['injury', 'Injury'], ['bullying', 'Bullying'], ['property', 'Property damage'], ['other', 'Other']];
export const SEVERITIES: Array<[string, string]> = [['minor', 'Minor'], ['moderate', 'Moderate'], ['serious', 'Serious'], ['critical', 'Critical']];
export const STATUS_LABEL: Record<string, string> = { open: 'Open', in_follow_up: 'In follow-up', closed: 'Closed' };

export interface FollowUp {
  id: string; incident: string; description: string; owner: string | null; owner_name: string; due_date: string;
  completed: boolean; completed_at: string | null; is_overdue: boolean;
}
export interface Incident {
  id: string; title: string; incident_date: string; incident_time: string | null; place: string; incident_type: string; severity: string;
  status: 'open' | 'in_follow_up' | 'closed'; students_involved: string[]; student_names: string[]; people_involved: string; description: string;
  witnesses: string; action_taken: string; notify_parents: boolean; parent_notified_at: string | null; closure_note: string; closed_at: string | null;
  reporter_name: string; follow_up_tasks: FollowUp[]; overdue_tasks: number; created_at: string;
}
export type IncidentInput = Partial<Pick<Incident, 'title' | 'incident_date' | 'incident_time' | 'place' | 'incident_type' | 'severity' | 'people_involved' | 'description' | 'witnesses' | 'action_taken' | 'notify_parents'>> & { students_involved?: string[] };

const safety = {
  async list(params: { status?: string; incident_type?: string; severity?: string } = {}): Promise<Incident[]> {
    return extractListData<Incident>((await api.get(`${base}/incidents/`, { params })).data);
  },
  async get(id: string): Promise<Incident> { return (await api.get(`${base}/incidents/${id}/`)).data; },
  async create(body: IncidentInput): Promise<Incident> { return (await api.post(`${base}/incidents/`, body)).data; },
  async update(id: string, body: IncidentInput): Promise<Incident> { return (await api.patch(`${base}/incidents/${id}/`, body)).data; },
  async addFollowUp(id: string, body: { description: string; due_date: string; owner?: string | null }): Promise<FollowUp> {
    return (await api.post(`${base}/incidents/${id}/add_follow_up/`, body)).data;
  },
  async completeTask(taskId: string): Promise<FollowUp> { return (await api.post(`${base}/follow-ups/${taskId}/complete/`)).data; },
  async close(id: string, closure_note: string): Promise<Incident> { return (await api.post(`${base}/incidents/${id}/close/`, { closure_note })).data; },
  async reopen(id: string): Promise<Incident> { return (await api.post(`${base}/incidents/${id}/reopen/`)).data; },
  async overdue(): Promise<Array<FollowUp & { incident_title: string }>> { return (await api.get(`${base}/incidents/overdue/`)).data; },
  async myTasks(): Promise<FollowUp[]> { return extractListData<FollowUp>((await api.get(`${base}/follow-ups/`, { params: { completed: false } })).data); },
};

export default safety;
