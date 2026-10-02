// Teaching rules (who may teach what), the timetable generator and cover. Leave lives in hr.service.ts.
import api, { extractListData } from './api';

const acad = '/auth/academics';

export interface SubjectRef { id: string; name: string; code: string }
export interface SchedulingPolicy {
  enforce_subject_match: boolean; max_periods_per_day: number; max_periods_per_week: number; max_consecutive: number;
  cover_allow_over_load: boolean;
}
export interface EligibleTeacher { id: string; name: string; relief: boolean; assigned: boolean; periods_per_week: number; reason?: string }
export interface EligibleResult { subject: string; class_name: string; qualified: EligibleTeacher[]; not_qualified: EligibleTeacher[] }
export interface CoverageReport {
  teachers_without_subjects: Array<{ id: string; name: string; text: string; relief: boolean }>;
  class_subjects_without_qualified_teacher: Array<{ class_subject: string; class_name: string; subject: string; periods_per_week: number }>;
  class_subjects_with_one_qualified_teacher: Array<{ class_subject: string; class_name: string; subject: string; periods_per_week: number; only: string }>;
  counts: { teachers: number; subjects: number; teachers_without_subjects: number; unstaffed: number };
}

export interface GenerateOptions { academic_year: string; commit?: boolean; seed?: number; classes?: string[] }
export interface Unscheduled { class_name: string; section: string; subject: string; missing: number; reason: string }
export interface Workload { teacher: string; periods: number; max_day: number; days: number }
export interface GeneratedSlot {
  class_name: string; subject: string; section: string; teacher: string; classroom: string; day_of_week: string;
  period_number: number | null; period_name: string;
}
export interface GenerateResult {
  status: string; committed: boolean; fitness_score: number; slots_scheduled: number; slots_requested: number;
  conflicts_resolved: boolean; slots?: GeneratedSlot[]; unscheduled?: Unscheduled[]; workloads?: Workload[];
  warnings?: string[]; snapshot_id?: string; seed?: number; error?: string;
}
export interface Snapshot { id: string; created_at: string; created_by: string; entries: number; academic_year: string; undone: boolean }

const scheduling = {
  policy: async () => (await api.get<SchedulingPolicy>(`${acad}/scheduling/policy/`)).data,
  savePolicy: async (b: Partial<SchedulingPolicy>) => (await api.patch<SchedulingPolicy>(`${acad}/scheduling/policy/`, b)).data,
  subjects: async () => extractListData<SubjectRef>((await api.get(`${acad}/subjects/`, { params: { page_size: 500 } })).data),
  teacherSubjects: async (teacherId: string) => (await api.get<{ subjects: SubjectRef[] }>(`${acad}/teachers/${teacherId}/subjects/`)).data.subjects,
  saveTeacherSubjects: async (teacherId: string, ids: string[]) =>
    (await api.put<{ subjects: SubjectRef[] }>(`${acad}/teachers/${teacherId}/subjects/`, { subjects: ids })).data.subjects,
  eligible: async (classSubjectId: string) => (await api.get<EligibleResult>(`${acad}/scheduling/eligible-teachers/`, { params: { class_subject: classSubjectId } })).data,
  coverage: async () => (await api.get<CoverageReport>(`${acad}/scheduling/coverage/`)).data,

  generate: async (o: GenerateOptions) => (await api.post<GenerateResult>('/ai/generate-timetable/', o)).data,
  snapshots: async (academicYear: string) => extractListData<Snapshot>((await api.get(`${acad}/timetable-snapshots/`, { params: { academic_year: academicYear } })).data),
  undo: async (id: string) => (await api.post<{ restored: number }>(`${acad}/timetable-snapshots/${id}/undo/`)).data,
};

export const errorText = (e: any, fallback: string) => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d.error === 'string') return d.error;
  if (typeof d.detail === 'string') return d.detail;
  const first = typeof d === 'object' ? Object.values(d)[0] : null;
  if (Array.isArray(first) && typeof first[0] === 'string') return first[0];
  return typeof first === 'string' ? first : fallback;
};

export default scheduling;
