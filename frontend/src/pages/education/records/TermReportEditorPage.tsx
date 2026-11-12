import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';
import termReports, { errorText, ReportContent, SubjectCell, TermReport } from '@/services/termReports.service';
import { btn, btnGhost, card, input, PageHead, Pill, Spinner } from '../hr/ui';

const VIEWPOINTS: Array<['v1' | 'v2' | 'v3', string]> = [['v1', '知識・技能'], ['v2', '思考・判断・表現'], ['v3', '主体的に学習に取り組む態度']];
const FIVE = ['5', '4', '3', '2', '1'];
const num = (v: string) => (v === '' ? null : Number(v));

/** One student's term report: ratings by subject, behaviour, attendance and comments, laid out by the school's layout. */
export default function TermReportEditorPage() {
  const { id = '' } = useParams();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [rep, setRep] = useState<TermReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [reopening, setReopening] = useState(false);

  useEffect(() => { termReports.get(id).then(setRep).catch((e) => toast.error(errorText(e, 'Could not load the report.'))); }, [id]);
  if (!rep) return <div className="p-6"><Spinner /></div>;
  const lay = rep.layout, locked = rep.is_locked;
  const set = (patch: Partial<TermReport>) => setRep({ ...rep, ...patch });
  const content: ReportContent = { subjects: rep.content.subjects || {}, conduct: rep.content.conduct || {}, comments: rep.content.comments || {} };
  const setContent = (c: ReportContent) => set({ content: c });
  const cell = (name: string): SubjectCell => content.subjects[name] || {};
  const setCell = (name: string, patch: SubjectCell) => setContent({ ...content, subjects: { ...content.subjects, [name]: { ...cell(name), ...patch } } });

  const run = async (fn: () => Promise<TermReport>, ok: string) => {
    setBusy(true);
    try { setRep(await fn()); toast.success(ok); } catch (e) { toast.error(errorText(e, 'That did not work.')); } finally { setBusy(false); }
  };
  const save = () => run(() => termReports.save(id, {
    class_name: rep.class_name, teacher_name: rep.teacher_name, principal_name: rep.principal_name, attendance_remarks: rep.attendance_remarks,
    school_days: rep.school_days, suspended_days: rep.suspended_days, absent_days: rep.absent_days, content }), 'Saved.');
  const ratingInput = (name: string) => lay.scale === 'percent'
    ? <input className={`${input} w-20`} inputMode="numeric" disabled={locked} aria-label={`${name} rating`} value={cell(name).rating || ''} onChange={(e) => setCell(name, { rating: e.target.value })} />
    : <select className={`${input} w-20`} disabled={locked} aria-label={`${name} rating`} value={cell(name).rating || ''} onChange={(e) => setCell(name, { rating: e.target.value })}>
        <option value="">-</option>{(lay.scale === 'abc' ? ['A', 'B', 'C'] : FIVE).map((v) => <option key={v} value={v}>{v}</option>)}
      </select>;

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title={`${rep.student_name} · ${rep.term_label}`} hint={`${rep.year_label} ${lay.title}`}>
        <Link to="/education/term-reports" className={btnGhost}>Back</Link>
        <Link to={`/education/term-reports/${id}/print`} className={btnGhost}>Print / PDF</Link>
        {!locked && <button className={btnGhost} disabled={busy} onClick={() => run(() => termReports.prefill(id), 'Filled from school data.')}>Fill from school data</button>}
        {!locked && <button className={btn} disabled={busy} onClick={save}>Save</button>}
        {!locked && <button className={btn} disabled={busy} onClick={() => run(async () => { await termReports.save(id, { class_name: rep.class_name, teacher_name: rep.teacher_name, content }); return termReports.finalise(id); }, 'The report is finalised.')}>Finalise</button>}
      </PageHead>
      {locked && (
        <div className={`${card} flex flex-wrap items-center gap-3 border-emerald-300`}>
          <Pill tone="green">Finalised</Pill><span className="text-sm text-slate-600">by {rep.finalised_by}. It cannot be changed unless an administrator re-opens it.</span>
          {isAdmin && !reopening && <button className={btnGhost} onClick={() => setReopening(true)}>Re-open…</button>}
          {isAdmin && reopening && (
            <span className="flex flex-wrap items-center gap-2">
              <input className={`${input} w-64`} placeholder="Why is it being re-opened?" value={reason} onChange={(e) => setReason(e.target.value)} />
              <button className={btn} disabled={busy || !reason.trim()} onClick={() => run(() => termReports.reopen(id, reason), 'The report is open again.')}>Re-open report</button>
            </span>
          )}
        </div>
      )}

      <section className={`${card} grid gap-3 sm:grid-cols-3`}>
        <label className="block text-xs font-bold text-slate-600">Class<input className={`${input} mt-1 font-normal`} disabled={locked} value={rep.class_name} onChange={(e) => set({ class_name: e.target.value })} /></label>
        <label className="block text-xs font-bold text-slate-600">Class teacher<input className={`${input} mt-1 font-normal`} disabled={locked} value={rep.teacher_name} onChange={(e) => set({ teacher_name: e.target.value })} /></label>
        <label className="block text-xs font-bold text-slate-600">Principal<input className={`${input} mt-1 font-normal`} disabled={locked} value={rep.principal_name} onChange={(e) => set({ principal_name: e.target.value })} /></label>
      </section>

      <section className={`${card} overflow-x-auto`} aria-label="Ratings by subject">
        <h2 className="font-bold text-sm mb-2">Ratings by subject</h2>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-500">
            <th className="py-2 pr-3">Subject</th>
            {lay.viewpoints && VIEWPOINTS.map(([k, label]) => <th key={k} className="pr-3">{label}</th>)}
            <th>Rating</th>
          </tr></thead>
          <tbody>
            {lay.subjects.map((name) => (
              <tr key={name} className="border-t border-slate-100">
                <td className="py-2 pr-3 font-semibold whitespace-nowrap">{name}</td>
                {lay.viewpoints && VIEWPOINTS.map(([k, label]) => (
                  <td key={k} className="pr-3">
                    <select className={`${input} w-20`} disabled={locked} aria-label={`${name} ${label}`} value={cell(name)[k] || ''} onChange={(e) => setCell(name, { [k]: e.target.value })}>
                      <option value="">-</option><option>A</option><option>B</option><option>C</option>
                    </select>
                  </td>
                ))}
                <td>{ratingInput(name)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {lay.sections.conduct && lay.conduct_items.length > 0 && (
        <section className={card} aria-label="Behaviour">
          <h2 className="font-bold text-sm mb-2">Behaviour (○ where it is a strength)</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {lay.conduct_items.map((item) => (
              <label key={item} className="flex items-center gap-2 text-sm">
                <input type="checkbox" disabled={locked} checked={!!content.conduct[item]} onChange={(e) => setContent({ ...content, conduct: { ...content.conduct, [item]: e.target.checked } })} />{item}
              </label>
            ))}
          </div>
        </section>
      )}

      {lay.sections.attendance && (
        <section className={`${card} grid gap-3 sm:grid-cols-4`} aria-label="Attendance">
          <label className="block text-xs font-bold text-slate-600">授業日数<input className={`${input} mt-1 font-normal`} inputMode="numeric" disabled={locked} value={rep.school_days ?? ''} onChange={(e) => set({ school_days: num(e.target.value) })} /></label>
          <label className="block text-xs font-bold text-slate-600">出席停止・忌引等<input className={`${input} mt-1 font-normal`} inputMode="numeric" disabled={locked} value={rep.suspended_days ?? ''} onChange={(e) => set({ suspended_days: num(e.target.value) })} /></label>
          <label className="block text-xs font-bold text-slate-600">欠席日数<input className={`${input} mt-1 font-normal`} inputMode="numeric" disabled={locked} value={rep.absent_days ?? ''} onChange={(e) => set({ absent_days: num(e.target.value) })} /></label>
          <label className="block text-xs font-bold text-slate-600">備考<input className={`${input} mt-1 font-normal`} disabled={locked} value={rep.attendance_remarks} onChange={(e) => set({ attendance_remarks: e.target.value })} /></label>
        </section>
      )}

      {lay.sections.comments && lay.comment_fields.map((c) => (
        <section key={c.key} className={card}>
          <label className="block text-xs font-bold text-slate-600">{c.label}
            <textarea className={`${input} mt-1 font-normal`} rows={4} disabled={locked} value={content.comments[c.key] || ''}
              onChange={(e) => setContent({ ...content, comments: { ...content.comments, [c.key]: e.target.value } })} />
          </label>
        </section>
      ))}
    </div>
  );
}
