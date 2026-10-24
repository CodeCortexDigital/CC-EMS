// Governed AI: approvals for what the assistant asks to do, and the school documents it may quote.
import api from './api';

const base = '/ai/governance';

export type RequestStatus = 'pending' | 'executed' | 'failed' | 'rejected' | 'expired';
export type Audience = 'everyone' | 'staff' | 'admin';

export interface ApprovalRequest {
  id: string; action: string; label: string; summary: string; status: RequestStatus;
  requested_by: string; requester_role: string; created_at: string; expires_at: string;
  decided_by: string; decided_at: string | null; decision_note: string;
  result: { note?: string; error?: string; [k: string]: unknown };
  approver_roles: string[]; can_decide: boolean;
}
export interface KnowledgeDoc { id: string; title: string; audience: Audience; is_active: boolean; passages: number; characters: number; updated_at: string; body?: string }
export interface Passage { document_id: string; title: string; ordinal: number; text: string; score: number }

export const STATUS_LABEL: Record<RequestStatus, string> = {
  pending: 'Waiting for approval', executed: 'Approved and done', failed: 'Approved, but it did not work', rejected: 'Rejected', expired: 'Expired',
};
export const AUDIENCE_LABEL: Record<Audience, string> = { everyone: 'Everyone', staff: 'Staff only', admin: 'Administrators only' };

const ai = {
  async approvals(status: 'pending' | 'all' = 'pending'): Promise<ApprovalRequest[]> { return (await api.get(`${base}/approvals/`, { params: { status } })).data; },
  async approve(id: string, note = ''): Promise<ApprovalRequest> { return (await api.post(`${base}/approvals/${id}/approve/`, { note })).data; },
  async reject(id: string, note = ''): Promise<ApprovalRequest> { return (await api.post(`${base}/approvals/${id}/reject/`, { note })).data; },
  async documents(): Promise<KnowledgeDoc[]> { return (await api.get(`${base}/knowledge/`)).data; },
  async document(id: string): Promise<KnowledgeDoc> { return (await api.get(`${base}/knowledge/${id}/`)).data; },
  async addDocument(body: { title: string; body: string; audience: Audience }): Promise<KnowledgeDoc> { return (await api.post(`${base}/knowledge/`, body)).data; },
  async editDocument(id: string, body: Partial<{ title: string; body: string; audience: Audience; is_active: boolean }>): Promise<KnowledgeDoc> {
    return (await api.patch(`${base}/knowledge/${id}/`, body)).data;
  },
  async removeDocument(id: string): Promise<void> { await api.delete(`${base}/knowledge/${id}/`); },
  async trySearch(query: string, asRole?: string): Promise<{ as_role: string; passages: Passage[] }> {
    return (await api.post(`${base}/knowledge/search/`, { query, ...(asRole ? { as_role: asRole } : {}) })).data;
  },
};

export default ai;
