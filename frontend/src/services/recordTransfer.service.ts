// Sending a 指導要録 to another school (転学 / 進学) and its retention. Server side: backend/services/education/records/transfer_views.py
// and retention.py (URLs under /auth/records/).
import api from './api';
import type { CumulativeRecord } from './records.service';

const base = '/auth/records';

export type TransferKind = 'transfer' | 'advance';
export interface Retention {
  left_on: string | null; counted_from: string | null; guidance_until: string | null; register_until: string | null; guidance_disposed_at: string | null;
}
export interface TransferRow { id: string; kind: TransferKind; kind_label: string; to_school: string; sent_on: string; note: string; issued_at: string; issued_by: string; snapshot?: CumulativeRecord }
export interface TransferInfo { problems: string[]; ready: boolean; retention: Retention; transfers: TransferRow[] }
export interface RetentionRow extends Retention {
  id: string; student_number: string; class_name: string; level: string; guidance_expired: boolean; register_expired: boolean;
}
export interface RetentionList { guidance_years: number; register_years: number; guidance_due: RetentionRow[]; register_due: RetentionRow[]; soon: RetentionRow[]; kept: number }

export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  if (!d) return fallback;
  const parts = [d.detail, ...(d.problems || []), d.kind, d.to_school, d.sent_on].filter((x) => typeof x === 'string');
  return parts.join(' ') || fallback;
};

const recordTransfer = {
  get: async (recordId: string) => (await api.get<TransferInfo>(`${base}/${recordId}/transfer/`)).data,
  send: async (recordId: string, body: { kind: TransferKind; to_school: string; sent_on: string; note: string }) => (await api.post<TransferRow>(`${base}/${recordId}/transfer/`, body)).data,
  issued: async (recordId: string, issueId: string) => (await api.get<TransferRow>(`${base}/${recordId}/transfer/${issueId}/`)).data,
  retention: async () => (await api.get<RetentionList>(`${base}/retention/`)).data,
  dispose: async (dispose: 'guidance' | 'register', ids: string[]) => (await api.post<{ disposed: number; part: string }>(`${base}/retention/`, { dispose, ids, confirm: ids.length })).data,
};

export default recordTransfer;
