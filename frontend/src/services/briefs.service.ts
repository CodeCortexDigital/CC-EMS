// Morning brief, evening summary and their weekly / fortnightly / monthly roll-ups (administrators only).
import api from './api';

const base = '/auth/briefs';

export type Kind = 'morning' | 'evening';
export type Period = 'week' | 'fortnight' | 'month';
export interface Item { key: string; label: string; value: number | null; unit: 'count' | 'money' | 'percent'; link: string; attention: boolean }
export interface Section { key: string; title: string; items: Item[] }
export interface Attention { key: string; label: string; value: number; link: string; section: string }

export interface BriefSummary {
  id: string; status: 'draft' | 'approved'; narrative_source: 'ai' | 'template'; edited: boolean; attention_count: number;
  approved_at: string | null; approved_by: string; read_by_me: boolean;
  kind?: Kind; date?: string;
  period?: Period; period_start?: string; period_end?: string; days?: number;
}
export interface Brief extends BriefSummary {
  narrative: string; original_narrative: string; generated_at: string; sections: Section[]; attention: Attention[]; approved_days?: number | null;
  /** The few figures for the one-screen version. */
  headline: Item[];
  /** Administrators who have marked it as read. */
  read_by: Array<{ name: string; at: string }>;
}
export interface BriefSettings { enabled: boolean; morning_time: string; evening_time: string; retention_days: number }
export interface Today { date: string; morning: Brief | null; evening: Brief | null; settings: BriefSettings; time_zone: string }

export const KIND_LABEL: Record<Kind, string> = { morning: 'Morning brief', evening: 'Evening summary' };
export const PERIOD_LABEL: Record<Period, string> = { week: 'Weekly', fortnight: 'Fortnightly', month: 'Monthly' };

const briefs = {
  async today(): Promise<Today> { return (await api.get(`${base}/today/`)).data; },
  async list(kind?: Kind): Promise<BriefSummary[]> { return (await api.get(`${base}/`, { params: kind ? { kind } : {} })).data; },
  async get(id: string): Promise<Brief> { return (await api.get(`${base}/${id}/`)).data; },
  async generate(kind: Kind, date?: string): Promise<Brief> { return (await api.post(`${base}/generate/`, { kind, ...(date ? { date } : {}) })).data; },
  async edit(id: string, narrative: string): Promise<Brief> { return (await api.patch(`${base}/${id}/`, { narrative })).data; },
  async approve(id: string, narrative?: string): Promise<Brief> { return (await api.post(`${base}/${id}/approve/`, narrative === undefined ? {} : { narrative })).data; },
  async remove(id: string): Promise<void> { await api.delete(`${base}/${id}/`); },
  async markRead(id: string): Promise<Brief> { return (await api.post(`${base}/${id}/read/`, {})).data; },
  async rollups(period?: Period): Promise<BriefSummary[]> { return (await api.get(`${base}/rollups/`, { params: period ? { period } : {} })).data; },
  async rollup(id: string): Promise<Brief> { return (await api.get(`${base}/rollups/${id}/`)).data; },
  async buildRollup(period: Period, end?: string): Promise<Brief> { return (await api.post(`${base}/rollups/generate/`, { period, ...(end ? { end } : {}) })).data; },
  async editRollup(id: string, narrative: string): Promise<Brief> { return (await api.patch(`${base}/rollups/${id}/`, { narrative })).data; },
  async approveRollup(id: string, narrative?: string): Promise<Brief> { return (await api.post(`${base}/rollups/${id}/approve/`, narrative === undefined ? {} : { narrative })).data; },
  async removeRollup(id: string): Promise<void> { await api.delete(`${base}/rollups/${id}/`); },
  async markRollupRead(id: string): Promise<Brief> { return (await api.post(`${base}/rollups/${id}/read/`, {})).data; },
  async settings(): Promise<BriefSettings> { return (await api.get(`${base}/settings/`)).data; },
  async saveSettings(body: Partial<BriefSettings>): Promise<BriefSettings> { return (await api.put(`${base}/settings/`, body)).data; },
};

export default briefs;
