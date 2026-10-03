// Health office: nurse visits, what medication a parent has allowed, and each dose given.
import api, { extractListData } from './api';

const base = '/education/students';

export const VISIT_TYPES: Array<[string, string]> = [
  ['illness', 'Illness'], ['injury', 'Injury'], ['medication', 'Medication'], ['assessment', 'Assessment'],
  ['emergency', 'Emergency'], ['follow-up', 'Follow-up'], ['screening', 'Screening'], ['other', 'Other'],
];
export const ACTIONS: Array<[string, string]> = [
  ['', 'Choose…'], ['treated', 'Treated at school'], ['rested', 'Rested and returned'], ['sent_home', 'Sent home'],
  ['hospital', 'Sent to hospital'], ['referred', 'Referred'], ['other', 'Other'],
];
export const ROUTES: Array<[string, string]> = [['oral', 'Oral'], ['topical', 'Topical'], ['inhaled', 'Inhaled'], ['injection', 'Injection'], ['other', 'Other']];
export const DOSE_STATUSES: Array<[string, string]> = [['given', 'Given'], ['refused', 'Refused'], ['missed', 'Missed'], ['held', 'Held'], ['error', 'Error']];

export interface HealthVisit {
  id: string; student: string; student_name: string; time_in: string; time_out: string | null; visit_type: string; complaint: string;
  action_taken: string; action_notes: string; sent_home: boolean; temperature: string | null; recorded_by_name: string; parent_notified_at: string | null;
}
export type VisitInput = Partial<Omit<HealthVisit, 'id' | 'student_name' | 'recorded_by_name' | 'parent_notified_at'>> & { student: string };

export interface MedicationAuthorization {
  id: string; student: string; student_name: string; medication_name: string; dose: string; route: string; times: string;
  min_hours_between_doses: number | null; start_date: string; end_date: string | null; instructions: string; prescriber: string;
  parent_consent: boolean; parent_consent_on: string | null; is_active: boolean; is_current: boolean;
}
export type AuthorizationInput = Partial<Omit<MedicationAuthorization, 'id' | 'student_name' | 'is_current' | 'parent_consent_on'>> & { student: string; medication_name: string; dose: string; start_date: string };

export interface MedicationLog {
  id: string; authorization: string; medication_name: string; student_name: string; given_at: string; status: string;
  dose_given: string; notes: string; override_reason: string; given_by_name: string;
}
export interface DoseInput { authorization: string; status: string; dose_given?: string; notes?: string; override_reason?: string; given_at?: string }

const health = {
  async visits(student?: string): Promise<HealthVisit[]> {
    return extractListData<HealthVisit>((await api.get(`${base}/health-visits/`, { params: student ? { student } : {} })).data);
  },
  async addVisit(body: VisitInput): Promise<HealthVisit> { return (await api.post(`${base}/health-visits/`, body)).data; },
  async authorizations(student?: string): Promise<MedicationAuthorization[]> {
    return extractListData<MedicationAuthorization>((await api.get(`${base}/medication-authorizations/`, { params: student ? { student } : {} })).data);
  },
  async addAuthorization(body: AuthorizationInput): Promise<MedicationAuthorization> { return (await api.post(`${base}/medication-authorizations/`, body)).data; },
  async updateAuthorization(id: string, body: Partial<AuthorizationInput>): Promise<MedicationAuthorization> {
    return (await api.patch(`${base}/medication-authorizations/${id}/`, body)).data;
  },
  async doses(authorization: string): Promise<MedicationLog[]> {
    return extractListData<MedicationLog>((await api.get(`${base}/medication-logs/`, { params: { authorization } })).data);
  },
  async giveDose(body: DoseInput): Promise<MedicationLog> { return (await api.post(`${base}/medication-logs/`, body)).data; },
};

export default health;
