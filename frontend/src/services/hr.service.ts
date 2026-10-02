// Staff & HR: cover requests, recruitment and onboarding, contracts and credentials, reviews and goals,
// pay setup, directory and org chart. Leave policy, carry-over and the leave calendar live under academics.
import api, { extractListData } from './api';

const base = '/auth/hr';
const acad = '/auth/academics';

export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d.error === 'string') return d.error;
  if (typeof d.detail === 'string') return d.detail;
  const first = typeof d === 'object' ? Object.values(d)[0] : null;
  if (Array.isArray(first) && typeof first[0] === 'string') return first[0];
  if (typeof first === 'string') return first;
  return fallback;
};

export interface PersonRef { id: string; name: string }
export interface CoverRequest {
  id: string; date: string; status: 'open' | 'filled' | 'cancelled';
  requester: PersonRef; substitute: PersonRef | null;
  period: { id: string; name: string; number: number; start: string; end: string } | null;
  class_name: string; subject: string; description: string; reason: string;
  filled_how: string; filled_at: string | null; created_at: string;
  can_accept: boolean; can_cancel: boolean; is_mine: boolean; is_covering: boolean;
}
export interface PeriodChoices {
  teacher: PersonRef | null;
  entries: Array<{ id: string; period: string; time: string; label: string; already_requested: boolean }>;
  periods: Array<{ id: string; name: string; time: string }>;
}
export interface CoverCandidate { id: string; name: string; relief: boolean; subject_match: boolean; qualified: boolean; reason: string; department: string }

export interface Alert {
  kind: 'contract_end' | 'probation_end' | 'credential'; teacher_id: string; teacher_name: string;
  date: string; what: string; days_left: number; expired: boolean;
}
export interface Overview {
  staff: number; on_leave_today: number; leave_waiting: number; cover_open: number; open_positions: number;
  candidates_active: number; onboarding_open: number; reviews_draft: number; alerts: Alert[]; alert_count: number; expired: number;
}

export interface Opening {
  id: string; title: string; department: string; description: string; positions: number; status: 'draft' | 'open' | 'closed';
  closes_on: string | null; candidate_count: number; hired_count: number;
}
export const STAGES = ['applied', 'screening', 'interview', 'offer', 'hired', 'rejected'] as const;
export type Stage = (typeof STAGES)[number];
export interface Candidate {
  id: string; opening: string; opening_title: string; full_name: string; email: string; phone: string; source: string;
  stage: Stage; rating: number | null; interview_at: string | null; notes: string;
  history: Array<{ at: string; by: string; from: string; to: string; note: string }>; staff: string | null;
}
export interface OnboardingTask { id: string; teacher: string; teacher_name: string; title: string; due_date: string | null; done: boolean; done_at: string | null; order: number }

export interface Contract {
  id: string; teacher: string; teacher_name: string; kind: string; start_date: string; end_date: string | null;
  probation_end: string | null; notes: string;
}
export interface Credential {
  id: string; teacher: string; teacher_name: string; name: string; issuer: string; number: string;
  issued_on: string | null; expires_on: string | null; notes: string;
}
export interface Review {
  id: string; teacher: string; teacher_name: string; reviewer_name: string; kind: string; period_label: string;
  review_date: string; rating: number | null; strengths: string; improvements: string; observed_class: string;
  employee_comment: string; status: 'draft' | 'shared' | 'acknowledged'; acknowledged_at: string | null;
}
export interface Goal {
  id: string; teacher: string; teacher_name: string; title: string; description: string; due_date: string | null;
  progress: number; status: 'open' | 'done' | 'dropped';
}

export interface Benefit { name: string; amount: string | number; kind: 'allowance' | 'deduction' }
export interface PayGrade { id: string; name: string; base_salary: string; notes: string; people: number }
export interface PayRow {
  teacher_id: string; name: string; employee_id: string; role: string; department: string; pay_grade: string | null;
  pay_grade_name: string; tax_rate_percent: number; benefits: Benefit[]; monthly_salary: number | null;
  basic: number; allowances: number; benefit_deductions: number; tax: number; deductions: number; net: number;
}

export interface Person {
  id: string; name: string; employee_id: string; role: string; department: string; email: string; phone: string;
  teacher_type: string; is_active: boolean; manager_id: string | null; manager_name: string;
}
export interface OrgNode extends Person { reports: OrgNode[] }

export interface MyHr {
  linked: boolean;
  teacher?: { id: string; name: string; role: string; department: string; manager: PersonRef | null };
  contracts?: Contract[]; credentials?: Credential[]; goals?: Goal[]; reviews?: Review[]; onboarding?: OnboardingTask[]; cover?: CoverRequest[];
}

export interface LeavePolicy { skip_weekends: boolean; skip_holidays: boolean; two_step_approval: boolean; carry_over_max_days: number }
export interface CalendarLeave {
  id: string; name: string; leave_type: string; day_part: string; status: string; start_date: string; end_date: string; days: number;
}
export interface LeaveCalendar { start: string; end: string; holidays: string[]; leaves: CalendarLeave[] }

const list = <T,>(p: Promise<{ data: unknown }>) => p.then((r) => extractListData<T>(r.data));

const hr = {
  overview: async () => (await api.get<Overview>(`${base}/overview/`)).data,
  alerts: async (days = 60) => (await api.get<Alert[]>(`${base}/alerts/`, { params: { days } })).data,
  me: async () => (await api.get<MyHr>(`${base}/me/`)).data,

  cover: {
    list: (params?: Record<string, string>) => list<CoverRequest>(api.get(`${base}/cover/`, { params })),
    create: async (body: Record<string, unknown>) => (await api.post<CoverRequest>(`${base}/cover/`, body)).data,
    absence: async (body: Record<string, unknown>) =>
      (await api.post<{ created: CoverRequest[]; already_covered: string[] }>(`${base}/cover/absence/`, body)).data,
    periods: async (date: string, teacherId?: string) =>
      (await api.get<PeriodChoices>(`${base}/cover/periods/`, { params: { date, teacher_id: teacherId } })).data,
    candidates: async (id: string) => (await api.get<CoverCandidate[]>(`${base}/cover/${id}/candidates/`)).data,
    act: async (id: string, action: 'accept' | 'assign' | 'release' | 'cancel', body?: Record<string, unknown>) =>
      (await api.post<CoverRequest>(`${base}/cover/${id}/${action}/`, body || {})).data,
  },

  openings: {
    list: (params?: Record<string, string>) => list<Opening>(api.get(`${base}/openings/`, { params })),
    create: async (b: Partial<Opening>) => (await api.post<Opening>(`${base}/openings/`, b)).data,
    update: async (id: string, b: Partial<Opening>) => (await api.patch<Opening>(`${base}/openings/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/openings/${id}/`),
  },
  candidates: {
    list: (params?: Record<string, string>) => list<Candidate>(api.get(`${base}/candidates/`, { params })),
    create: async (b: Partial<Candidate>) => (await api.post<Candidate>(`${base}/candidates/`, b)).data,
    update: async (id: string, b: Partial<Candidate>) => (await api.patch<Candidate>(`${base}/candidates/${id}/`, b)).data,
    stage: async (id: string, stage: Stage, note = '', interview_at?: string) =>
      (await api.post<Candidate>(`${base}/candidates/${id}/stage/`, { stage, note, interview_at })).data,
    hire: async (id: string, body: { joining_date?: string; email?: string; employee_id?: string }) =>
      (await api.post<{ teacher_id: string; employee_id: string; onboarding_tasks: number }>(`${base}/candidates/${id}/hire/`, body)).data,
  },
  onboarding: {
    list: (params?: Record<string, string>) => list<OnboardingTask>(api.get(`${base}/onboarding/`, { params })),
    start: async (teacher_id: string) => (await api.post<{ created: number }>(`${base}/onboarding/start/`, { teacher_id })).data,
    toggle: async (id: string, done: boolean) => (await api.patch<OnboardingTask>(`${base}/onboarding/${id}/`, { done })).data,
    update: async (id: string, b: Partial<OnboardingTask>) => (await api.patch<OnboardingTask>(`${base}/onboarding/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/onboarding/${id}/`),
    add: async (b: Partial<OnboardingTask>) => (await api.post<OnboardingTask>(`${base}/onboarding/`, b)).data,
  },

  contracts: {
    list: (params?: Record<string, string>) => list<Contract>(api.get(`${base}/contracts/`, { params })),
    create: async (b: Partial<Contract>) => (await api.post<Contract>(`${base}/contracts/`, b)).data,
    update: async (id: string, b: Partial<Contract>) => (await api.patch<Contract>(`${base}/contracts/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/contracts/${id}/`),
  },
  credentials: {
    list: (params?: Record<string, string>) => list<Credential>(api.get(`${base}/credentials/`, { params })),
    create: async (b: Partial<Credential>) => (await api.post<Credential>(`${base}/credentials/`, b)).data,
    update: async (id: string, b: Partial<Credential>) => (await api.patch<Credential>(`${base}/credentials/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/credentials/${id}/`),
  },

  reviews: {
    list: (params?: Record<string, string>) => list<Review>(api.get(`${base}/reviews/`, { params })),
    create: async (b: Partial<Review>) => (await api.post<Review>(`${base}/reviews/`, b)).data,
    update: async (id: string, b: Partial<Review>) => (await api.patch<Review>(`${base}/reviews/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/reviews/${id}/`),
    acknowledge: async (id: string, comment: string) => (await api.post<Review>(`${base}/reviews/${id}/acknowledge/`, { comment })).data,
  },
  goals: {
    list: (params?: Record<string, string>) => list<Goal>(api.get(`${base}/goals/`, { params })),
    create: async (b: Partial<Goal>) => (await api.post<Goal>(`${base}/goals/`, b)).data,
    update: async (id: string, b: Partial<Goal>) => (await api.patch<Goal>(`${base}/goals/${id}/`, b)).data,
    remove: async (id: string) => api.delete(`${base}/goals/${id}/`),
  },

  pay: {
    grades: () => list<PayGrade>(api.get(`${base}/payroll/grades/`)),
    createGrade: async (b: { name: string; base_salary: string | number; notes?: string }) => (await api.post<PayGrade>(`${base}/payroll/grades/`, b)).data,
    updateGrade: async (id: string, b: Partial<PayGrade>) => (await api.patch<PayGrade>(`${base}/payroll/grades/${id}/`, b)).data,
    removeGrade: async (id: string) => api.delete(`${base}/payroll/grades/${id}/`),
    profiles: async () => (await api.get<PayRow[]>(`${base}/payroll/profiles/`)).data,
    saveProfile: async (teacherId: string, b: { pay_grade?: string | null; tax_rate_percent?: string | number; benefits?: Benefit[] }) =>
      (await api.patch<PayRow>(`${base}/payroll/profiles/${teacherId}/`, b)).data,
  },

  directory: async (includeInactive = false) =>
    (await api.get<Person[]>(`${base}/directory/`, { params: includeInactive ? { include_inactive: 1 } : {} })).data,
  orgChart: async () => (await api.get<{ tree: OrgNode[]; count: number }>(`${base}/org-chart/`)).data,
  setManager: async (teacherId: string, managerId: string | null) =>
    (await api.post<Person>(`${base}/directory/${teacherId}/manager/`, { manager_id: managerId })).data,

  leave: {
    policy: async () => (await api.get<LeavePolicy>(`${acad}/leave-policy/`)).data,
    savePolicy: async (b: Partial<LeavePolicy>) => (await api.patch<LeavePolicy>(`${acad}/leave-policy/`, b)).data,
    carryOver: async (year?: number) =>
      (await api.post<{ year: number; limit: number; carried: Array<{ name: string; days: number }> }>(`${acad}/leave-balances/carry-over/`, year ? { year } : {})).data,
    days: async (start: string, end: string, dayPart = 'full') =>
      (await api.get<{ days: number }>(`${acad}/leave-days/`, { params: { start, end, day_part: dayPart } })).data.days,
    calendar: async (start: string, end: string) => (await api.get<LeaveCalendar>(`${acad}/leave-calendar/`, { params: { start, end } })).data,
  },
};

export const LEAVE_TYPES: Array<{ key: string; label: string }> = [
  { key: 'sick', label: 'Sick' }, { key: 'casual', label: 'Casual' }, { key: 'annual', label: 'Annual / vacation' },
  { key: 'personal', label: 'Personal day' }, { key: 'bereavement', label: 'Bereavement' }, { key: 'jury', label: 'Jury duty' },
  { key: 'professional', label: 'Professional development' }, { key: 'maternity', label: 'Maternity / parental' },
  { key: 'emergency', label: 'Emergency' }, { key: 'unpaid', label: 'Unpaid' }, { key: 'other', label: 'Other' },
];
export const leaveTypeLabel = (k: string) => LEAVE_TYPES.find((t) => t.key === k)?.label || k;

export default hr;
