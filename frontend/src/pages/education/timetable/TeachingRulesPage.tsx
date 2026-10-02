import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import SubjectPicker from '@/components/teacher/SubjectPicker';
import scheduling, { CoverageReport, errorText, SchedulingPolicy } from '@/services/scheduling.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-4';
const input = 'w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm text-center';

function PolicyCard() {
  const [p, setP] = useState<SchedulingPolicy | null>(null);
  useEffect(() => { scheduling.policy().then(setP).catch(() => toast.error('Could not load the teaching rules.')); }, []);
  if (!p) return null;
  const save = async (patch: Partial<SchedulingPolicy>) => {
    const next = { ...p, ...patch };
    setP(next);
    try { setP(await scheduling.savePolicy(patch)); toast.success('Teaching rules saved.'); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); setP(p); }
  };
  const num = (key: 'max_periods_per_day' | 'max_periods_per_week' | 'max_consecutive', label: string, hint: string) => (
    <label className="text-xs font-bold text-slate-700 block">
      {label}
      <input aria-label={label} type="number" min={1} max={60} className={`${input} mt-1 block`} defaultValue={p[key]}
        onBlur={(e) => { const v = parseInt(e.target.value, 10); if (v && v !== p[key]) save({ [key]: v }); }} />
      <span className="font-normal text-slate-400">{hint}</span>
    </label>
  );
  return (
    <div className={card}>
      <h2 className="font-bold text-sm mb-3 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-700" />Teaching rules</h2>
      <div className="grid gap-4 md:grid-cols-5">
        <label className="flex items-start gap-2 text-xs md:col-span-2">
          <input type="checkbox" className="mt-0.5" checked={p.enforce_subject_match} onChange={(e) => save({ enforce_subject_match: e.target.checked })} />
          <span><b className="text-slate-700">Only qualified teachers teach a subject</b>
            <span className="block text-slate-400">Assignments, timetable slots, the generator and substitute cover all follow this.</span></span>
        </label>
        {num('max_periods_per_day', 'Most periods a day', 'per teacher')}
        {num('max_periods_per_week', 'Most periods a week', 'per teacher')}
        {num('max_consecutive', 'Most in a row', 'before a free period')}
        <label className="flex items-start gap-2 text-xs md:col-span-5">
          <input type="checkbox" className="mt-0.5" checked={p.cover_allow_over_load} onChange={(e) => save({ cover_allow_over_load: e.target.checked })} />
          <span><b className="text-slate-700">Allow cover by a qualified teacher who is at their weekly limit</b>
            <span className="block text-slate-400">Off: when nobody qualified has room, the period becomes an open cover request for HR instead.</span></span>
        </label>
      </div>
    </div>
  );
}

function BareTeacher({ t, onSaved }: { t: CoverageReport['teachers_without_subjects'][number]; onSaved: () => void }) {
  const [ids, setIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try { await scheduling.saveTeacherSubjects(t.id, ids); toast.success(`Saved subjects for ${t.name}.`); onSaved(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <li className="py-3 border-b border-slate-100 last:border-0">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="font-semibold text-sm">{t.name}</span>
        {t.relief && <span className="text-[10px] font-bold rounded-full bg-sky-100 text-sky-800 px-2">relief</span>}
        {t.text && <span className="text-xs text-slate-400">on file: "{t.text}"</span>}
        <button disabled={ids.length === 0 || saving} onClick={save} className="ml-auto px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 text-white disabled:opacity-40">Save</button>
      </div>
      <SubjectPicker value={ids} onChange={setIds} />
    </li>
  );
}

export default function TeachingRulesPage() {
  const [report, setReport] = useState<CoverageReport | null>(null);
  const load = useCallback(() => { scheduling.coverage().then(setReport).catch(() => setReport(null)); }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div>
        <h1 className="text-xl font-black text-slate-900">Teaching rules and coverage</h1>
        <p className="text-sm text-slate-500 max-w-3xl">Say who is qualified to teach which subject. The timetable generator, manual timetable edits and substitute cover only ever use qualified teachers, so fix the gaps below first.</p>
      </div>
      <PolicyCard />
      {!report ? <p className="text-sm text-slate-500">Loading…</p> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[['Active teachers', report.counts.teachers], ['Subjects', report.counts.subjects],
              ['Teachers with no subjects', report.counts.teachers_without_subjects], ['Subjects nobody can teach', report.counts.unstaffed]].map(([l, v]) => (
              <div key={String(l)} className={card}><p className="text-2xl font-black">{v}</p><p className="text-xs text-slate-500">{l}</p></div>
            ))}
          </div>

          {report.class_subjects_without_qualified_teacher.length > 0 && (
            <div className={`${card} border-rose-300`}>
              <h2 className="font-bold text-sm mb-2 flex items-center gap-2 text-rose-800"><AlertTriangle className="w-4 h-4" />Nobody is qualified to teach these</h2>
              <ul className="text-sm divide-y divide-slate-100">
                {report.class_subjects_without_qualified_teacher.map((r) => (
                  <li key={r.class_subject} className="py-1.5">{r.class_name} · <b>{r.subject}</b> <span className="text-slate-400">({r.periods_per_week} periods a week will not be timetabled)</span></li>
                ))}
              </ul>
            </div>
          )}

          <div className={card}>
            <h2 className="font-bold text-sm mb-1">Teachers with no subjects set</h2>
            <p className="text-xs text-slate-500 mb-2">These people cannot be given lessons or cover until you say what they teach.</p>
            {report.teachers_without_subjects.length === 0
              ? <p className="text-sm text-emerald-700 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />Everyone has subjects.</p>
              : <ul>{report.teachers_without_subjects.map((t) => <BareTeacher key={t.id} t={t} onSaved={load} />)}</ul>}
          </div>

          {report.class_subjects_with_one_qualified_teacher.length > 0 && (
            <div className={card}>
              <h2 className="font-bold text-sm mb-1">Only one qualified teacher</h2>
              <p className="text-xs text-slate-500 mb-2">If they are away there is nobody else qualified to cover. Consider qualifying a second teacher.</p>
              <ul className="text-sm divide-y divide-slate-100">
                {report.class_subjects_with_one_qualified_teacher.map((r) => (
                  <li key={r.class_subject} className="py-1.5">{r.class_name} · <b>{r.subject}</b> <span className="text-slate-400">only {r.only}</span></li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
