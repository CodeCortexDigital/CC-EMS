// Admissions extras: the waiting list and seat offers, tours and interviews, the document checklist and the application
// fee. The first half is for school administrators; the second half is what a family does with its tracking code.
import api, { extractListData } from './api';

const base = '/auth/admissions';

export interface WaitlistConfig {
  id: string; class_name: string; academic_year: string; capacity: number; offer_hours: number;
  sibling_priority: boolean; staff_child_priority: boolean; seats_taken: number; open_offers: number; seats_left: number; waiting: number;
}
export type WaitlistConfigInput = Partial<Pick<WaitlistConfig, 'class_name' | 'academic_year' | 'capacity' | 'offer_hours' | 'sibling_priority' | 'staff_child_priority'>>;
export interface WaitlistEntry {
  id: string; application: string; application_no: string; student_name: string; grade: string; sibling: boolean;
  staff_child: boolean; joined_at: string; status: string; position?: number;
}
export interface Offer { id: string; entry: string; application_no: string; student_name: string; offered_at: string; expires_at: string; status: string; responded_at: string | null }

export interface TourSlot {
  id: string; kind: 'tour' | 'interview'; starts_at: string; ends_at: string; location: string; host: string; capacity: number;
  is_open: boolean; booked: number; seats_left: number;
}
export type TourSlotInput = Partial<Pick<TourSlot, 'kind' | 'starts_at' | 'ends_at' | 'location' | 'host' | 'capacity' | 'is_open'>>;
export interface TourBooking { id: string; slot: string; kind: string; starts_at: string; application: string; application_no: string; student_name: string; status: string }

export type DocState = 'missing' | 'uploaded' | 'received' | 'redo';
export interface ChecklistItem { name: string; state: DocState; document: { id: string; name: string; url: string } | null; note: string }

const asList = <T,>(r: { data: unknown }) => extractListData<T>(r.data);

const extras = {
  // ---- waiting list
  async configs(): Promise<WaitlistConfig[]> { return asList(await api.get(`${base}/waitlist-configs/`)); },
  async saveConfig(id: string | null, body: WaitlistConfigInput): Promise<WaitlistConfig> {
    return (id ? await api.patch(`${base}/waitlist-configs/${id}/`, body) : await api.post(`${base}/waitlist-configs/`, body)).data;
  },
  async deleteConfig(id: string) { await api.delete(`${base}/waitlist-configs/${id}/`); },
  async entries(id: string): Promise<{ config: WaitlistConfig; entries: WaitlistEntry[] }> { return (await api.get(`${base}/waitlist-configs/${id}/entries/`)).data; },
  async addToList(id: string, application: string, staff_child: boolean): Promise<WaitlistEntry> {
    return (await api.post(`${base}/waitlist-configs/${id}/add/`, { application, staff_child })).data;
  },
  async fill(id: string): Promise<{ offers_made: number }> { return (await api.post(`${base}/waitlist-configs/${id}/fill/`)).data; },
  async removeEntry(id: string) { await api.post(`${base}/waitlist-entries/${id}/remove/`); },
  async setStaffChild(id: string, staff_child: boolean) { await api.patch(`${base}/waitlist-entries/${id}/`, { staff_child }); },
  async offers(status = 'offered'): Promise<Offer[]> { return asList(await api.get(`${base}/offers/`, { params: { status } })); },
  async withdrawOffer(id: string) { await api.post(`${base}/offers/${id}/withdraw/`); },

  // ---- tours and interviews
  async slots(params: { kind?: string } = {}): Promise<TourSlot[]> { return asList(await api.get(`${base}/tour-slots/`, { params })); },
  async saveSlot(id: string | null, body: TourSlotInput): Promise<TourSlot> {
    return (id ? await api.patch(`${base}/tour-slots/${id}/`, body) : await api.post(`${base}/tour-slots/`, body)).data;
  },
  async deleteSlot(id: string) { await api.delete(`${base}/tour-slots/${id}/`); },
  async bookings(slot?: string): Promise<TourBooking[]> { return asList(await api.get(`${base}/tour-bookings/`, { params: { status: 'booked', ...(slot ? { slot } : {}) } })); },
  async cancelBooking(id: string) { await api.post(`${base}/tour-bookings/${id}/cancel/`); },

  // ---- documents and fee, per application
  async checklist(appId: string): Promise<{ items: ChecklistItem[]; complete: boolean }> { return (await api.get(`${base}/applications/${appId}/checklist/`)).data; },
  async reviewDocument(appId: string, docId: string, status: 'received' | 'redo', note = '') {
    return (await api.post(`${base}/applications/${appId}/documents/${docId}/review/`, { status, note })).data;
  },
  async waiveFee(appId: string, note: string) { await api.post(`${base}/applications/${appId}/fee/waive/`, { note }); },
  async markFeePaid(appId: string, reference: string) { await api.post(`${base}/applications/${appId}/fee/mark-paid/`, { reference }); },
};

export default extras;

// ---------------------------------------------------------------------------------------------------------------------
// Families: no login, only the application number and tracking code.
// ---------------------------------------------------------------------------------------------------------------------

export interface Credentials { no: string; token: string }
export interface FamilyOffer { application_no: string; student: string; grade: string; status: string; offer: { id: string; expires_at: string } | null }
export interface FamilyTours { slots: TourSlot[]; my_bookings: TourBooking[] }
export interface FamilyFee { fee: { amount: string; currency: string; status: 'unpaid' | 'paid' | 'waived' } | null }

export const family = {
  async offer(c: Credentials): Promise<FamilyOffer> { return (await api.get(`${base}/public/offer/`, { params: c })).data; },
  async respond(c: Credentials, decision: 'accept' | 'decline') { return (await api.post(`${base}/public/offer/`, { ...c, decision })).data; },
  async tours(c: Credentials, kind: 'tour' | 'interview'): Promise<FamilyTours> { return (await api.get(`${base}/public/tours/`, { params: { ...c, kind } })).data; },
  async book(c: Credentials, slot: string): Promise<TourBooking> { return (await api.post(`${base}/public/tours/`, { ...c, slot })).data; },
  async cancelBooking(c: Credentials, booking: string) { return (await api.post(`${base}/public/tours/cancel/`, { ...c, booking })).data; },
  async documents(c: Credentials): Promise<{ items: ChecklistItem[] }> { return (await api.get(`${base}/public/documents/`, { params: c })).data; },
  async upload(c: Credentials, doc_type: string, file: File): Promise<{ items: ChecklistItem[] }> {
    const form = new FormData();
    form.append('no', c.no); form.append('token', c.token); form.append('doc_type', doc_type); form.append('file', file);
    return (await api.post(`${base}/public/documents/`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
  async fee(c: Credentials): Promise<FamilyFee> { return (await api.get(`${base}/public/fee/`, { params: c })).data; },
  async checkout(c: Credentials, success_url: string, cancel_url: string): Promise<{ url: string }> {
    return (await api.post(`${base}/public/fee/checkout/`, { ...c, success_url, cancel_url })).data;
  },
};
