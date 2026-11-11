import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/hooks/useAuth';
import records, {
  Course, CumulativeRecord, errorText, LEVEL_LABEL, RecordYear, SubjectCell, YearContent, YearInput,
} from '@/services/records.service';
import { btn, btnDanger, btnGhost, card, Empty, Field, fmtDate, input, PageHead, Pill, Spinner } from '../hr/ui';

type Tab = 'register' | 'learning' | 'activities' | 'attendance';
const TABS: Array<[Tab, string]> = [['register', 'Register (様式1)'], ['learning', 'Learning record (様式2)'], ['activities', 'Activities & behaviour'], ['attendance', 'Attendance & seals']];
const MARKS = ['', 'A', 'B', 'C'];

/** What the year form edits; built from the server's year (or a blank one before the first save). */
interface Draft {
  year_label: string; class_name: string; roll_number: string; teacher_name: string; principal_name: string;
  school_days: number | null; suspended_days: number | null; abroad_days: number | null; absent_days: number | null;
  attendance_remarks: string; content: YearContent;
}
const toDraft = (y: RecordYear | undefined, rec: CumulativeRecord): Draft => ({
  year_label: y?.year_label ?? '', class_name: y?.class_name ?? rec.class_name ?? '', roll_number: y?.roll_number ?? '',
  teacher_name: y?.teacher_name ?? '', principal_name: y?.principal_name ?? '',
  school_days: y?.school_days ?? null, suspended_days: y?.suspended_days ?? null, abroad_days: y?.abroad_days ?? null, absent_days: y?.absent_days ?? null,
  attendance_remarks: y?.attendance_remarks ?? '', content: JSON.parse(JSON.stringify(y?.content ?? {})),
});

const REGISTER_TEXT: Array<[keyof CumulativeRecord, string]> = [
  ['student_furigana', 'Student furigana (ふりがな)'], ['student_address', 'Student address (現住所)'],
  ['guardian_name', 'Guardian name (保護者氏名)'], ['guardian_furigana', 'Guardian furigana'], ['guardian_address', 'Guardian address'],
  ['school_name', 'School name (学校名)'], ['school_address', 'School address (所在地)'],
];

export default function RecordEditorPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [rec, setRec] = useState<CumulativeRecord | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab>('register');
  const [grade, setGrade] = useState(1);
  const [reg, setReg] = useState<Partial<CumulativeRecord>>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [reopening, setReopening] = useState(false);
  const [reason, setReason] = useState('');

  useEffect(() => {
    records.get(id).then((r) => { setRec(r); setReg(r); }).catch(() => setFailed(true));
  }, [id]);

  const year = rec?.years.find((y) => y.grade === grade);
  // Reset the year draft whenever the chosen year (or the server's copy of it) changes.
  useEffect(() => { if (rec) setDraft(toDraft(year, rec)); }, [rec, year, grade]);

  const applyYear = useCallback((y: RecordYear) => {
    setRec((r) => (r ? { ...r, years: [...r.years.filter((x) => x.grade !== y.grade), y].sort((a, b) => a.grade - b.grade) } : r));
  }, []);

  const run = async (fn: () => Promise<RecordYear>, ok: string) => {
    setBusy(true);
    try { applyYear(await fn()); toast.success(ok); } catch (e) { toast.error(errorText(e, 'That did not work.')); } finally { setBusy(false); }
  };

  const def = rec?.definition;
  const subjects = useMemo(() => (def?.subjects ?? []).filter((s) => s.grades.includes(grade)), [def, grade]);

  if (failed) return <div className="p-6"><Empty>This record could not be opened.</Empty></div>;
  if (!rec || !def || !draft) return <Spinner />;

  const locked = !!year?.locked;
  const high = rec.level === 'high';
  const setD = (patch: Partial<Draft>) => setDraft((d) => (d ? { ...d, ...patch } : d));
  const setC = (patch: Partial<YearContent>) => setDraft((d) => (d ? { ...d, content: { ...d.content, ...patch } } : d));
  const cell = (code: string): SubjectCell => draft.content.subjects?.[code] ?? {};
  const setCell = (code: string, patch: Partial<SubjectCell>) => setC({ subjects: { ...draft.content.subjects, [code]: { ...cell(code), ...patch } } });
  const courses = draft.content.courses ?? [];
  const setCourse = (i: number, patch: Partial<Course>) => setC({ courses: courses.map((c, k) => (k === i ? { ...c, ...patch } : c)) });
  const credits = courses.reduce((n, c) => n + (Number(c.credits) || 0), 0);
  const num = (v: string) => (v === '' ? null : Number(v));
  const ratingOpts = ['', ...Array.from({ length: def.rating_max }, (_, i) => String(i + 1))];

  const saveRegister = async () => {
    setBusy(true);
    try {
      const patch: Record<string, unknown> = {};
      REGISTER_TEXT.forEach(([k]) => { patch[k] = reg[k] ?? ''; });
      ['previous_history', 'transfer_out_note', 'next_school', 'next_work', 'course_name', 'entry_kind', 'level'].forEach((k) => { patch[k] = (reg as any)[k] ?? ''; });
      ['entry_date', 'transfer_in_date', 'transfer_out_date', 'graduation_date', 'abroad_from', 'abroad_to'].forEach((k) => { patch[k] = (reg as any)[k] || null; });
      patch.entry_grade = Number(reg.entry_grade) || 1;
      patch.transfer_in_grade = reg.transfer_in_grade ? Number(reg.transfer_in_grade) : null;
      const r = await records.update(rec.id, patch as Partial<CumulativeRecord>);
      setRec(r); setReg(r); toast.success('Register saved.');
    } catch (e) { toast.error(errorText(e, 'Could not save the register.')); } finally { setBusy(false); }
  };

  const saveYear = () => {
    const body: YearInput = { ...draft };
    return run(() => records.saveYear(rec.id, grade, body), `Year ${grade} saved.`);
  };

  const doReopen = async () => {
    if (!reason.trim()) return;
    await run(() => records.reopen(rec.id, grade, reason.trim()), 'Year re-opened.');
    setReopening(false); setReason('');
  };

  const text = (k: keyof CumulativeRecord, label: string, type = 'text') => (
    <Field label={label}><input type={type} className={input} value={String(reg[k] ?? '')} onChange={(e) => setReg({ ...reg, [k]: e.target.value })} /></Field>
  );
  const area = (k: keyof Draft, label: string, v: string | number | null, nm: boolean) => (
    <Field label={label}>
      <input className={input} disabled={locked} type={nm ? 'number' : 'text'} min={nm ? 0 : undefined} value={v ?? ''}
        onChange={(e) => setD({ [k]: nm ? num(e.target.value) : e.target.value } as Partial<Draft>)} />
    </Field>
  );
  const textarea = (label: string, key: keyof YearContent, limit?: number) => (
    <Field label={label}>
      <textarea className={input} rows={3} disabled={locked} maxLength={limit} value={(draft.content[key] as string) ?? ''} onChange={(e) => setC({ [key]: e.target.value })} />
    </Field>
  );
  const select = (label: string, value: string | number | undefined, opts: string[], onChange: (v: string) => void) => (
    <select aria-label={label} className={input} disabled={locked} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
      {opts.map((o) => <option key={o} value={o}>{o || '-'}</option>)}
    </select>
  );
  const limit = (k: string) => def.text_limits?.[k];

  const yearChips = (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Year">
      {Array.from({ length: def.grades }, (_, i) => i + 1).map((g) => {
        const sealed = rec.years.find((y) => y.grade === g)?.locked;
        return (
          <button key={g} aria-pressed={grade === g} onClick={() => setGrade(g)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold border ${grade === g ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>
            {g}年{sealed ? ' ✔' : ''}
          </button>
        );
      })}
    </div>
  );

  const lockBanner = locked && (
    <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm font-bold text-amber-900">Locked: the principal has sealed this year</div>
  );
  const saveBar = (
    <div className="flex justify-end"><button className={btn} disabled={busy || locked} onClick={saveYear}>Save year</button></div>
  );

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title={rec.student_name} hint={`${rec.student_number} · ${rec.class_name || 'No class'} · ${LEVEL_LABEL[rec.level]}`}>
        <Link className={btnGhost} to={`/education/records/${rec.id}/print`}>Print / PDF</Link>
        <button className={btnGhost} onClick={() => records.downloadCsv(rec.id).catch((e) => toast.error(errorText(e, 'Could not export.')))}>Export CSV</button>
        <button className={btnGhost} onClick={() => navigate('/education/records')}>Back</button>
      </PageHead>

      <div className="flex flex-wrap gap-2" role="tablist">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold border ${tab === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{l}</button>
        ))}
      </div>

      {tab === 'register' && (
        <div className={`${card} space-y-4`}>
          <div className="grid gap-3 sm:grid-cols-3 text-sm">
            <div><span className="text-xs font-bold text-slate-600">Name (氏名)</span><p>{rec.student_name}</p></div>
            <div><span className="text-xs font-bold text-slate-600">Gender (性別)</span><p>{/^f/i.test(rec.gender) ? '女' : /^m/i.test(rec.gender) ? '男' : rec.gender || '-'}</p></div>
            <div><span className="text-xs font-bold text-slate-600">Date of birth (生年月日)</span><p>{fmtDate(rec.date_of_birth) || '-'}</p></div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Level (学校種)">
              <select className={input} value={reg.level ?? rec.level} onChange={(e) => setReg({ ...reg, level: e.target.value as CumulativeRecord['level'] })}>
                {Object.entries(LEVEL_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </Field>
            {REGISTER_TEXT.map(([k, l]) => <div key={k}>{text(k, l)}</div>)}
            {high && text('course_name', 'Course name (課程・学科)')}
            <Field label="Entry kind (入学/編入学)">
              <select className={input} value={reg.entry_kind ?? 'enrolled'} onChange={(e) => setReg({ ...reg, entry_kind: e.target.value as 'enrolled' | 'admitted' })}>
                <option value="enrolled">入学</option><option value="admitted">編入学</option>
              </select>
            </Field>
            {text('entry_date', 'Entry date', 'date')}
            {text('entry_grade', 'Entry grade (学年)', 'number')}
            {text('transfer_in_date', 'Transfer in date (転入学)', 'date')}
            {text('transfer_in_grade', 'Transfer in grade', 'number')}
            {text('transfer_out_date', 'Transfer out date (転学・退学)', 'date')}
            {text('transfer_out_note', 'Transfer out note')}
            {text('graduation_date', 'Graduation date (卒業)', 'date')}
            {text('next_school', 'Next school (進学先)')}
            {rec.level !== 'elementary' && text('next_work', 'Next work (就職先)')}
            {high && text('abroad_from', 'Abroad from (留学)', 'date')}
            {high && text('abroad_to', 'Abroad to', 'date')}
          </div>
          <Field label="Previous history (入学前の経歴)"><textarea className={input} rows={3} value={reg.previous_history ?? ''} onChange={(e) => setReg({ ...reg, previous_history: e.target.value })} /></Field>
          <div className="flex justify-end"><button className={btn} disabled={busy} onClick={saveRegister}>Save register</button></div>
        </div>
      )}

      {tab !== 'register' && <>{yearChips}{lockBanner}</>}

      {tab === 'learning' && (
        <div className={`${card} space-y-4`}>
          <div className="grid gap-3 sm:grid-cols-3">
            {area('year_label', 'Year label (年度)', draft.year_label, false)}
            {area('class_name', 'Class (学級)', draft.class_name, false)}
            {area('roll_number', 'Roll number (整理番号)', draft.roll_number, false)}
            {area('teacher_name', 'Class teacher (担任者氏名)', draft.teacher_name, false)}
            {area('principal_name', 'Principal (校長氏名)', draft.principal_name, false)}
          </div>

          {!high && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500">
                    <th className="py-2 pr-3">教科</th>
                    {def.viewpoints.map((v) => <th key={v.key} className="pr-2">観点: {v.label}</th>)}
                    <th>評定</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((s) => (
                    <tr key={s.code} className="border-t border-slate-100">
                      <td className="py-2 pr-3 font-semibold whitespace-nowrap">{s.name}</td>
                      {def.viewpoints.map((v) => (
                        <td key={v.key} className="pr-2">{select(`${s.name} ${v.label}`, cell(s.code)[v.key], MARKS, (x) => setCell(s.code, { [v.key]: x }))}</td>
                      ))}
                      <td>{s.rating_grades.includes(grade) && select(`${s.name} 評定`, cell(s.code).rating, ratingOpts, (x) => setCell(s.code, { rating: x ? Number(x) : undefined }))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {high && (
            <div className="space-y-3">
              {courses.length === 0 && <p className="text-sm text-slate-500">No courses yet.</p>}
              {courses.map((c, i) => (
                <div key={i} className="grid gap-2 sm:grid-cols-3 lg:grid-cols-[1.2fr_1.5fr_repeat(3,0.6fr)_0.6fr_0.6fr_auto] items-end border-t border-slate-100 pt-2">
                  <Field label="教科 (area)">
                    <select className={input} disabled={locked} value={c.area} onChange={(e) => setCourse(i, { area: e.target.value })}>
                      <option value="">-</option>{def.high_subject_areas.map((a) => <option key={a} value={a}>{a}</option>)}
                    </select>
                  </Field>
                  <Field label="科目 (course)"><input className={input} disabled={locked} value={c.course} onChange={(e) => setCourse(i, { course: e.target.value })} /></Field>
                  {def.viewpoints.map((v) => <Field key={v.key} label={`観点: ${v.label}`}>{select(`Course ${i + 1} ${v.label}`, c[v.key], MARKS, (x) => setCourse(i, { [v.key]: x }))}</Field>)}
                  <Field label="評定">{select(`Course ${i + 1} 評定`, c.rating, ratingOpts, (x) => setCourse(i, { rating: x ? Number(x) : undefined }))}</Field>
                  <Field label="単位数 (credits)"><input type="number" min={0} className={input} disabled={locked} value={c.credits ?? ''} onChange={(e) => setCourse(i, { credits: num(e.target.value) ?? undefined })} /></Field>
                  <button className={btnDanger} disabled={locked} aria-label={`Remove course ${i + 1}`} onClick={() => setC({ courses: courses.filter((_, k) => k !== i) })}><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
              <div className="flex items-center gap-3">
                <button className={btnGhost} disabled={locked} onClick={() => setC({ courses: [...courses, { area: '', course: '' }] })}><Plus className="inline w-3.5 h-3.5 mr-1" />Add course</button>
                <span className="text-sm font-bold">Credits total: {credits}</span>
              </div>
            </div>
          )}

          {def.moral_grades.includes(grade) && textarea('道徳 (moral education)', 'moral', limit('moral'))}
          {def.integrated_grades.includes(grade) && (
            <div className="grid gap-3 sm:grid-cols-3">
              {textarea('総合的な学習の時間: 学習活動', 'integrated_activity', limit('integrated_activity'))}
              {textarea('総合的な学習の時間: 観点', 'integrated_viewpoint', limit('integrated_viewpoint'))}
              {textarea('総合的な学習の時間: 評価', 'integrated_evaluation', limit('integrated_evaluation'))}
            </div>
          )}
          {def.foreign_activity_grades.includes(grade) && (
            <div className="grid gap-3 sm:grid-cols-3">
              {def.viewpoints.map((v, i) => <div key={v.key}>{textarea(`外国語活動: ${v.label}`, (['foreign_v1', 'foreign_v2', 'foreign_v3'] as const)[i], limit(`foreign_v${i + 1}`))}</div>)}
            </div>
          )}
          {saveBar}
        </div>
      )}

      {tab === 'activities' && (
        <div className={`${card} space-y-4`}>
          <fieldset>
            <legend className="text-sm font-black mb-2">特別活動の記録 (special activities)</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {def.special_activities.map((a) => (
                <label key={a.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" disabled={locked} checked={!!draft.content.special_activities?.[a.key]}
                    onChange={(e) => setC({ special_activities: { ...draft.content.special_activities, [a.key]: e.target.checked } })} />{a.label} ○
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="text-sm font-black mb-2">行動の記録 (behaviour)</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {def.behaviour_items.map((a) => (
                <label key={a.key} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" disabled={locked} checked={!!draft.content.behaviour?.[a.key]}
                    onChange={(e) => setC({ behaviour: { ...draft.content.behaviour, [a.key]: e.target.checked } })} />{a.label} ○
                </label>
              ))}
            </div>
          </fieldset>
          {textarea('総合所見及び指導上参考となる諸事項 (comment)', 'comment', limit('comment'))}
          {saveBar}
        </div>
      )}

      {tab === 'attendance' && (
        <div className={`${card} space-y-4`}>
          <div className="grid gap-3 sm:grid-cols-3">
            {area('school_days', '授業日数 (school days)', draft.school_days, true)}
            {area('suspended_days', '出席停止・忌引等の日数', draft.suspended_days, true)}
            {high && area('abroad_days', '留学中の授業日数', draft.abroad_days, true)}
            {area('absent_days', '欠席日数 (absent)', draft.absent_days, true)}
            <div><span className="text-xs font-bold text-slate-600">出席しなければならない日数 (required)</span><p className="text-lg font-black" data-testid="required">{year?.required_days ?? '-'}</p></div>
            <div><span className="text-xs font-bold text-slate-600">出席日数 (present)</span><p className="text-lg font-black" data-testid="present">{year?.present_days ?? '-'}</p></div>
          </div>
          {area('attendance_remarks', '備考 (remarks)', draft.attendance_remarks, false)}
          <div className="flex flex-wrap items-center gap-3">
            <button className={btnGhost} disabled={busy || locked} onClick={() => run(() => records.prefillYear(rec.id, grade), 'Filled from school data.')}>Fill from school data</button>
            <p className="text-xs text-slate-500 max-w-xl">Counts the school days, absences and suspensions from the attendance register for this year. You can still change the numbers afterwards.</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-200 p-3 text-sm">
              <p className="font-bold mb-1">Class teacher seal (印)</p>
              {year?.teacher_confirmed_at ? <Pill tone="green">{year.teacher_confirmed_by} · {fmtDate(year.teacher_confirmed_at)}</Pill> : <Pill tone="slate">Not sealed</Pill>}
            </div>
            <div className="rounded-lg border border-slate-200 p-3 text-sm">
              <p className="font-bold mb-1">Principal seal (印)</p>
              {year?.principal_confirmed_at ? <Pill tone="green">{year.principal_confirmed_by} · {fmtDate(year.principal_confirmed_at)}</Pill> : <Pill tone="slate">Not sealed</Pill>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className={btnGhost} disabled={busy || locked || !year || !!year.teacher_confirmed_at} onClick={() => run(() => records.seal(rec.id, grade, 'teacher'), 'Sealed as class teacher.')}>Seal as class teacher</button>
            {isAdmin && <button className={btnGhost} disabled={busy || locked || !year?.teacher_confirmed_at} onClick={() => run(() => records.seal(rec.id, grade, 'principal'), 'Sealed as principal.')}>Seal as principal</button>}
            {isAdmin && locked && <button className={btnDanger} disabled={busy} onClick={() => setReopening(true)}>Re-open…</button>}
          </div>
          {!year && <p className="text-xs text-slate-500">Save the year first, then it can be sealed.</p>}
          {saveBar}
        </div>
      )}

      <Modal open={reopening} onClose={() => setReopening(false)} title={`Re-open year ${grade}`} footer={
        <><button className={btnGhost} onClick={() => setReopening(false)}>Cancel</button><button className={btn} disabled={busy || !reason.trim()} onClick={doReopen}>Re-open year</button></>
      }>
        <Field label="Reason (required)"><textarea className={input} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      </Modal>
    </div>
  );
}
