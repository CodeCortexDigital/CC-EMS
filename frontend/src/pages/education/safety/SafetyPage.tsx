import { useCallback, useEffect, useState } from 'react';
import { AlertOctagon, CheckCircle2, Plus, X } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import StudentPicker from '@/components/common/StudentPicker';
import { btn, btnDanger, btnGhost, card, Empty, errorText, Field, fmtDate, input, PageHead, Pill, Spinner, todayStr } from '@/components/common/kit';
import { useAuth } from '@/hooks/useAuth';
import api from '@/services/api';
import safety, { INCIDENT_TYPES, Incident, SEVERITIES, STATUS_LABEL } from '@/services/safety.service';
import type { StudentHit } from '@/services/frontdesk.service';

const sevTone = (s: string) => (s === 'critical' || s === 'serious' ? 'red' : s === 'moderate' ? 'amber' : 'slate') as 'red' | 'amber' | 'slate';

export default function SafetyPage() {
  const { role } = useAuth();
  const reviewer = role === 'admin' || role === 'counsellor';
  const [rows, setRows] = useState<Incident[] | null>(null);
  const [status, setStatus] = useState('');
  const [open, setOpen] = useState<string | null>(null);
  const [reporting, setReporting] = useState(false);

  const load = useCallback(() => { setRows(null); safety.list(status ? { status } : {}).then(setRows).catch(() => setRows([])); }, [status]);
  useEffect(load, [load]);

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Safety reports" hint={reviewer ? 'Every report, with follow-up. Reports are never deleted.' : 'Report an injury, bullying or damage. You can see your own reports here.'}>
        <select aria-label="Filter by status" className="rounded-lg border border-slate-300 px-3 py-2 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button className={btn} onClick={() => setReporting(true)}><Plus className="inline w-3.5 h-3.5 mr-1" />Report an incident</button>
      </PageHead>

      {reviewer && <OverduePanel onOpen={setOpen} />}

      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>No reports yet.</Empty> : (
        <ul className="space-y-2">
          {rows.map((i) => (
            <li key={i.id}>
              <button className={`${card} w-full text-left hover:border-emerald-400`} onClick={() => setOpen(i.id)}>
                <div className="flex flex-wrap items-center gap-2">
                  <AlertOctagon className="w-4 h-4 text-slate-500" />
                  <b className="text-sm">{i.title}</b>
                  <Pill tone={sevTone(i.severity)}>{i.severity}</Pill>
                  <Pill tone={i.status === 'closed' ? 'green' : i.status === 'in_follow_up' ? 'blue' : 'amber'}>{STATUS_LABEL[i.status]}</Pill>
                  {i.overdue_tasks > 0 && <Pill tone="red">{i.overdue_tasks} overdue</Pill>}
                  <span className="text-xs text-slate-400 ml-auto">{fmtDate(i.incident_date)}{reviewer && i.reporter_name && ` · ${i.reporter_name}`}</span>
                </div>
                {i.student_names.length > 0 && reviewer && <p className="text-xs text-slate-500 mt-1">Involving {i.student_names.join(', ')}</p>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {reporting && <ReportDialog onClose={() => setReporting(false)} onDone={() => { setReporting(false); load(); }} />}
      {open && <DetailDialog id={open} reviewer={reviewer} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}

function OverduePanel({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<Array<{ id: string; incident: string; description: string; due_date: string; owner_name: string; incident_title: string }>>([]);
  useEffect(() => { safety.overdue().then(setRows as any).catch(() => setRows([])); }, []);
  if (rows.length === 0) return null;
  return (
    <div className="rounded-xl border border-rose-300 bg-rose-50 p-3" role="alert">
      <p className="font-bold text-rose-900 text-sm mb-1">{rows.length} follow-up task{rows.length > 1 ? 's are' : ' is'} overdue</p>
      <ul className="text-sm space-y-0.5">
        {rows.map((t) => <li key={t.id}><button className="underline" onClick={() => onOpen(t.incident)}>{t.incident_title}</button>: {t.description} · due {fmtDate(t.due_date)}{t.owner_name && ` · ${t.owner_name}`}</li>)}
      </ul>
    </div>
  );
}

function ReportDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ title: '', incident_date: todayStr(), incident_time: '', place: '', incident_type: 'injury', severity: 'minor', people_involved: '', description: '', witnesses: '', action_taken: '', notify_parents: false });
  const [students, setStudents] = useState<StudentHit[]>([]);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setSaving(true);
    try {
      await safety.create({ ...f, incident_time: f.incident_time || null, students_involved: students.map((s) => s.id) });
      toast.success('Report filed.');
      onDone();
    } catch (e) { toast.error(errorText(e, 'Could not file the report.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title="Report an incident" size="lg">
      <div className="space-y-3">
        <Field label="What happened (short title)"><input aria-label="Title" className={input} value={f.title} onChange={set('title')} /></Field>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <Field label="Date"><input aria-label="Date" type="date" className={input} value={f.incident_date} onChange={set('incident_date')} /></Field>
          <Field label="Time"><input aria-label="Time" type="time" className={input} value={f.incident_time} onChange={set('incident_time')} /></Field>
          <Field label="Type"><select aria-label="Type" className={input} value={f.incident_type} onChange={set('incident_type')}>{INCIDENT_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="Severity"><select aria-label="Severity" className={input} value={f.severity} onChange={set('severity')}>{SEVERITIES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        </div>
        <Field label="Where"><input aria-label="Place" className={input} value={f.place} onChange={set('place')} /></Field>
        <div>
          <p className="text-xs font-bold text-slate-600 mb-1">Students involved</p>
          <StudentPicker onPick={(s) => setStudents((cur) => (cur.some((c) => c.id === s.id) ? cur : [...cur, s]))} label="Add a student" />
          <div className="flex flex-wrap gap-1 mt-2">
            {students.map((s) => <span key={s.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs">{s.name}<button aria-label={`Remove ${s.name}`} onClick={() => setStudents(students.filter((x) => x.id !== s.id))}><X className="w-3 h-3" /></button></span>)}
          </div>
        </div>
        <Field label="Other people involved"><input aria-label="Other people" className={input} value={f.people_involved} onChange={set('people_involved')} placeholder="Staff, visitors, or names not in the system" /></Field>
        <Field label="Description"><textarea aria-label="Description" className={input} rows={3} value={f.description} onChange={set('description')} /></Field>
        <div className="grid md:grid-cols-2 gap-2">
          <Field label="Witnesses"><input aria-label="Witnesses" className={input} value={f.witnesses} onChange={set('witnesses')} /></Field>
          <Field label="Action taken"><input aria-label="Action taken" className={input} value={f.action_taken} onChange={set('action_taken')} /></Field>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.notify_parents} onChange={(e) => setF({ ...f, notify_parents: e.target.checked })} />Tell the parents of the students involved</label>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !f.title.trim() || !f.description.trim()} onClick={save}>File report</button></div>
      </div>
    </Modal>
  );
}

function DetailDialog({ id, reviewer, onClose, onChanged }: { id: string; reviewer: boolean; onClose: () => void; onChanged: () => void }) {
  const [inc, setInc] = useState<Incident | null>(null);
  const [owners, setOwners] = useState<Array<{ id: string; name: string }>>([]);
  const [task, setTask] = useState({ description: '', due_date: todayStr(), owner: '' });
  const [note, setNote] = useState('');
  const [closing, setClosing] = useState(false);

  const load = useCallback(() => { safety.get(id).then(setInc).catch(() => onClose()); }, [id, onClose]);
  useEffect(load, [load]);
  useEffect(() => { if (reviewer) api.get('/auth/safety/incidents/owners/').then((r) => setOwners(r.data)).catch(() => setOwners([])); }, [reviewer]);
  const refresh = () => { load(); onChanged(); };

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast.success(ok); refresh(); } catch (e) { toast.error(errorText(e, 'That did not work.')); }
  };

  if (!inc) return <Modal open onClose={onClose} title="Incident"><Spinner /></Modal>;
  const closed = inc.status === 'closed';

  return (
    <Modal open onClose={onClose} title={inc.title} size="lg">
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2">
          <Pill tone={sevTone(inc.severity)}>{inc.severity}</Pill><Pill tone="blue">{INCIDENT_TYPES.find(([k]) => k === inc.incident_type)?.[1]}</Pill>
          <Pill tone={closed ? 'green' : 'amber'}>{STATUS_LABEL[inc.status]}</Pill>
          <span className="text-slate-500 text-xs ml-auto">{fmtDate(inc.incident_date)}{inc.incident_time && ` ${inc.incident_time.slice(0, 5)}`} · {inc.place || 'place not given'} · reported by {inc.reporter_name || 'unknown'}</span>
        </div>
        <p>{inc.description}</p>
        {inc.student_names.length > 0 && <p><b>Students:</b> {inc.student_names.join(', ')}{inc.parent_notified_at && ' · parents told'}</p>}
        {inc.people_involved && <p><b>Others:</b> {inc.people_involved}</p>}
        {inc.witnesses && <p><b>Witnesses:</b> {inc.witnesses}</p>}
        {inc.action_taken && <p><b>Action taken:</b> {inc.action_taken}</p>}
        {closed && <p className="rounded-lg bg-emerald-50 border border-emerald-200 p-3"><CheckCircle2 className="inline w-4 h-4 text-emerald-700 mr-1" /><b>Closed:</b> {inc.closure_note}</p>}

        <section aria-label="Follow-up">
          <h3 className="font-bold mb-1">Follow-up</h3>
          {inc.follow_up_tasks.length === 0 ? <p className="text-slate-500">No follow-up tasks.</p> : (
            <ul className="divide-y divide-slate-100">
              {inc.follow_up_tasks.map((t) => (
                <li key={t.id} className="py-1.5 flex items-center gap-2">
                  <span className={t.completed ? 'line-through text-slate-400' : ''}>{t.description}</span>
                  <span className="text-xs text-slate-500">due {fmtDate(t.due_date)}{t.owner_name && ` · ${t.owner_name}`}</span>
                  {t.is_overdue && <Pill tone="red">overdue</Pill>}
                  {!t.completed && reviewer && <button className={`${btnGhost} ml-auto`} onClick={() => run(() => safety.completeTask(t.id), 'Marked done.')}>Mark done</button>}
                </li>
              ))}
            </ul>
          )}
          {reviewer && !closed && (
            <div className="grid gap-2 md:grid-cols-4 mt-2">
              <input aria-label="Task" className={`${input} md:col-span-2`} placeholder="What needs doing" value={task.description} onChange={(e) => setTask({ ...task, description: e.target.value })} />
              <input aria-label="Due date" type="date" className={input} value={task.due_date} onChange={(e) => setTask({ ...task, due_date: e.target.value })} />
              <select aria-label="Owner" className={input} value={task.owner} onChange={(e) => setTask({ ...task, owner: e.target.value })}>
                <option value="">No owner</option>{owners.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
              <button className={`${btn} md:col-span-4`} disabled={!task.description.trim()}
                onClick={() => run(() => safety.addFollowUp(inc.id, { description: task.description, due_date: task.due_date, owner: task.owner || null }).then(() => setTask({ description: '', due_date: todayStr(), owner: '' })), 'Task added.')}>Add task</button>
            </div>
          )}
        </section>

        {reviewer && (
          <div className="flex flex-wrap gap-2 justify-end border-t border-slate-100 pt-3">
            {closed ? <button className={btnGhost} onClick={() => run(() => safety.reopen(inc.id), 'Reopened.')}>Reopen</button> : closing ? (
              <div className="w-full space-y-2">
                <textarea aria-label="Closure note" className={input} rows={2} placeholder="How was this resolved?" value={note} onChange={(e) => setNote(e.target.value)} />
                <div className="flex justify-end gap-2"><button className={btnGhost} onClick={() => setClosing(false)}>Cancel</button><button className={btnDanger} disabled={!note.trim()} onClick={() => run(() => safety.close(inc.id, note), 'Closed.')}>Close incident</button></div>
              </div>
            ) : <button className={btnGhost} onClick={() => setClosing(true)}>Close incident…</button>}
          </div>
        )}
      </div>
    </Modal>
  );
}
