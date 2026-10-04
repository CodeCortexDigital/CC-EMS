// Planning reports for the office: next year's enrolment, score trends, staff signals, and a written read of the figures.
import api from './api';

export interface ForecastRow {
  grade: number; label: string; this_year: number; from_below: number; confirmed: number; pipeline: number; expected: number; low: number; high: number;
  seats: number | null; seats_left: number | null; sections_needed: number; class_size: number;
}
export interface Forecast {
  year: string; grades: ForecastRow[]; total: { this_year: number; expected: number; low: number; high: number };
  assumptions: { retention: number; retention_assumed: boolean; conversion: number; conversion_assumed: boolean; how: string };
  unmatched_applications: number;
}
export interface TrendGroup { name: string; change: number; declining: boolean; series: Array<{ term: string; term_name: string; average: number | null; students: number }> }
export interface Trends { by: 'subject' | 'class'; terms: Array<{ id: string; name: string }>; groups: TrendGroup[]; declining: number; hidden_groups: number; min_group: number; note: string }
export interface StaffSignal { kind: string; label: string; detail: string }
export interface Staffing { staff: Array<{ teacher_id: string; teacher_name: string; signals: StaffSignal[] }>; counts: Record<string, number>; active_staff: number; note: string }
export type NarrativeReport = 'overview' | 'attendance' | 'finance' | 'enrolment';
export interface Narrative { report: NarrativeReport; title: string; period: string; summary: string; source: 'ai' | 'template'; cached?: boolean; facts: Array<{ label: string; value: string | number; change?: string | null }> }

const planning = {
  async forecast(year = ''): Promise<Forecast> { return (await api.get('/auth/insights/forecast/', { params: year ? { year } : {} })).data; },
  async trends(by: 'subject' | 'class'): Promise<Trends> { return (await api.get('/auth/insights/trends/', { params: { by } })).data; },
  async staffing(): Promise<Staffing> { return (await api.get('/auth/hr/signals/')).data; },
  async narrative(report: NarrativeReport): Promise<Narrative> { return (await api.post('/auth/insights/narrative/', { report })).data; },
};

export default planning;
