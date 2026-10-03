// Front desk: who may collect a student, the release log, and the visitor sign-in book.
import api, { extractListData } from './api';

const base = '/education/students';

export interface StudentHit { id: string; student_id: string; name: string; class_name: string }

export interface PickupGuardian {
  kind: 'guardian'; id: string; name: string; relationship: string; phone: string; can_pickup: boolean; custody_notes: string;
}
export interface PickupAdult {
  kind: 'adult'; id: string; name: string; relationship: string; phone: string; photo_path: string; id_type: string;
  id_checked: boolean; do_not_release: boolean; court_order_note: string;
}
export interface PickupList {
  student: { id: string; name: string; student_id: string };
  guardians: PickupGuardian[];
  authorized_adults: PickupAdult[];
}

export interface AdultInput {
  student: string; name: string; relationship?: string; phone?: string; id_type?: string; id_checked?: boolean;
  do_not_release?: boolean; court_order_note?: string;
}
export interface ReleaseInput {
  student: string; authorized_adult?: string; guardian?: string; id_confirmed: boolean; reason?: string;
  early_dismissal?: boolean; override_reason?: string;
}
export interface Release {
  id: string; student: string; student_name: string; released_to_name: string; released_at: string; early_dismissal: boolean;
  reason: string; override_used: boolean; override_reason: string; released_by_name: string;
}

export interface Visitor {
  id: string; name: string; organisation: string; visiting: string; purpose: string; badge_number: string;
  checked_in_at: string; checked_out_at: string | null; on_site: boolean;
}
export type VisitorInput = Partial<Pick<Visitor, 'name' | 'organisation' | 'visiting' | 'purpose' | 'badge_number'>>;

const frontDesk = {
  /** Find a student by name or student number (works for every staff role, unlike the main student list). */
  async findStudents(q: string): Promise<StudentHit[]> {
    return (await api.get(`${base}/lookup/`, { params: { q } })).data;
  },
  async pickupList(student: string): Promise<PickupList> {
    return (await api.get(`${base}/pickup-list/`, { params: { student } })).data;
  },
  async addAdult(body: AdultInput) { return (await api.post(`${base}/authorized-adults/`, body)).data as PickupAdult; },
  async updateAdult(id: string, body: Partial<AdultInput>) { return (await api.patch(`${base}/authorized-adults/${id}/`, body)).data as PickupAdult; },
  async removeAdult(id: string) { await api.delete(`${base}/authorized-adults/${id}/`); },
  async release(body: ReleaseInput): Promise<Release> { return (await api.post(`${base}/pickup-releases/`, body)).data; },
  async releases(student?: string): Promise<Release[]> {
    return extractListData<Release>((await api.get(`${base}/pickup-releases/`, { params: student ? { student } : {} })).data);
  },

  async visitors(params: { on_site?: boolean; date_from?: string; date_to?: string } = {}): Promise<Visitor[]> {
    const query: Record<string, string> = {};
    if (params.on_site) query.on_site = '1';
    if (params.date_from) query.date_from = params.date_from;
    if (params.date_to) query.date_to = params.date_to;
    return extractListData<Visitor>((await api.get(`${base}/visitors/`, { params: query })).data);
  },
  async signIn(body: VisitorInput): Promise<Visitor> { return (await api.post(`${base}/visitors/`, body)).data; },
  async signOut(id: string): Promise<Visitor> { return (await api.post(`${base}/visitors/${id}/check_out/`)).data; },
};

export default frontDesk;
