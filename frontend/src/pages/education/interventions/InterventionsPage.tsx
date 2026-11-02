import { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import StudentPicker from '@/components/common/StudentPicker';
import { btn, btnDanger, btnGhost, card, Empty, errorText, Field, fmtDate, fmtDateTime, input, PageHead, Pill, Spinner, todayStr } from '@/components/common/kit';
import { useAuth } from '@/hooks/useAuth';
import type { StudentHit } from '@/services/frontdesk.service';
import interventions, { Intervention, Owner, SOURCE_LABEL, STATUS_LABEL, Summary, Reach, Outcome, OUTCOME_LABEL } from '@/services/interventions.service';

type View = 'active' | 'mine' | 'overdue' | 'unassigned' | 'closed';
const VIEWS: Array<[View, string]> = [['active', 'All active'], ['mine', 'Mine'], ['overdue', 'Overdue'], ['unassigned', 'Unassigned'], ['closed', 'Closed']];

const statusTone = (s: string) => (s === 'done' ? 'green' : s === 'dismissed' ? 'slate' : s === 'in_progress' ? 'blue' : 'amber') as 'green' | 'slate' | 'blue' | 'amber';

export default function InterventionsPage() {
  const { role } = useAuth();
  const reviewer = role === 'admin' || role === 'counsellor';
  const [view, setView] = useState<View>(reviewer ? 'active' : 'mine');
  const [search, setSearch] = useState('');
  const [rows, setRows] = useState<Intervention[] | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [reach, setReach] = useState<Reach | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    const f = view === 'mine' ? { owner: 'me', active: true } : view === 'overdue' ? { overdue: true } : view === 'unassigned' ? { owner: 'none', active: true }
      : view === 'closed' ? { status: 'done' } : { active: true };
    setRows(null);
    interventions.list({ ...f, search: search.trim() || undefined }).then(setRows).catch(() => setRows([]));
    interventions.summary().then(setSummary).catch(() => setSummary(null));
    if (reviewer) interventions.reach().then(setReach).catch(() => setReach(null));
  }, [view, search, reviewer]);
  useEffect(() => { const t = window.setTimeout(load, 200); return () => window.clearTimeout(t); }, [load]);

  const tiles: Array<[string, number | undefined, View | null, string]> = [
    ['Open', summary ? summary.open + summary.in_progress : undefined, 'active', 'text-slate-900'],
    ['Overdue', summary?.overdue, 'overdue', 'text-rose-700'],
    ['Unassigned', summary?.unassigned, 'unassigned', 'text-amber-700'],
    ['Mine', summary?.mine, 'mine', 'text-emerald-700'],
  ];

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Interventions" hint={reviewer ? 'What the school is doing about individual students. They open automatically when absences add up or the early-warning model flags a student, and you can add your own.' : 'Interventions assigned to you.'}>
        {reviewer && <button className={btn} onClick={() => setAdding(true)}><Plus className="inline w-3.5 h-3.5 mr-1" />New intervention</button>}
      </PageHead>

      {reviewer && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {tiles.map(([label, value, target, tone]) => (
            <button key={label} className={`${card} text-left hover:border-emerald-400`} onClick={() => target && setView(target)} aria-label={`${label}: ${value ?? ''}`}>
              <p className={`text-2xl font-black ${tone}`}>{value ?? '–'}</p><p className="text-xs text-slate-500">{label}</p>
            </button>
          ))}
        </div>
      )}

      {reviewer && reach && <ReachPanel reach={reach} />}

      <div className="flex flex-wrap items-center gap-2">
        {VIEWS.filter(([v]) => reviewer || v === 'mine' || v === 'closed' || v === 'overdue').map(([v, l]) => (
          <button key={v} onClick={() => setView(v)} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${view === v ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300 text-slate-700'}`}>{l}</button>
        ))}
        <input aria-label="Search" className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Search a student or title" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>{view === 'mine' ? 'Nothing is assigned to you.' : 'No interventions here.'}</Empty> : (
        <ul className="space-y-2">
          {rows.map((i) => (
            <li key={i.id}>
              <button className={`${card} w-full text-left hover:border-emerald-400`} onClick={() => setOpenId(i.id)}>
                <div className="flex flex-wrap items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-slate-500" />
                  <b className="text-sm">{i.student_name}</b><span className="text-xs text-slate-400">{i.class_name}</span>
                  <span className="text-sm text-slate-700">{i.title}</span>
                  {i.priority === 'high' && <Pill tone="red">high</Pill>}
                  <Pill tone="slate">{SOURCE_LABEL[i.source]}</Pill>
                  <Pill tone={statusTone(i.status)}>{STATUS_LABEL[i.status]}</Pill>
                  {i.is_overdue && <Pill tone="red">overdue</Pill>}
                  {i.is_review_due && <Pill tone="amber">review due</Pill>}
                  <span className="text-xs text-slate-500 ml-auto">{i.owner_name ? `Owner: ${i.owner_name}` : 'No owner'}{i.due_date && ` · due ${fmtDate(i.due_date)}`}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {adding && <NewDialog onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
      {openId && <DetailDialog id={openId} reviewer={reviewer} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}

function ReachPanel({ reach }: { reach: Reach }) {
  const results = (Object.keys(OUTCOME_LABEL) as Outcome[]).filter((k) => reach.results[k] > 0).map((k) => `${reach.results[k]} ${OUTCOME_LABEL[k].toLowerCase()}`);
  const facts: Array<[string, string]> = [
    ['Students flagged', String(reach.students_flagged)],
    ['Students reached', String(reach.students_reached)],
    ['Sessions delivered', String(reach.sessions_delivered)],
    ['Days from flag to start', reach.average_days_to_start === null ? '–' : String(reach.average_days_to_start)],
    ['Reviews due', String(reach.reviews_due)],
  ];
  return (
    <section aria-label="Reach and results" className={`${card} space-y-2`}>
      <p className="text-sm font-bold">Who the support has reached</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {facts.map(([label, value]) => <div key={label}><p className="text-xl font-black text-slate-900">{value}</p><p className="text-xs text-slate-500">{label}</p></div>)}
      </div>
      <p className="text-xs text-slate-500">
        {reach.closed === 0 ? 'No support has been finished yet, so there are no results to show.'
          : `Finished: ${reach.closed}${results.length ? ` (${results.join(', ')})` : ''}${reach.closed_without_result ? `. ${reach.closed_without_result} finished without a result recorded.` : '.'}`}
      </p>
    </section>
  );
}

function NewDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [student, setStudent] = useState<StudentHit | null>(null);
  const [f, setF] = useState({ title: '', description: '', priority: 'normal' as 'normal' | 'high', owner: '', due_date: '' });
  const [owners, setOwners] = useState<Owner[]>([]);
  const [saving, setSaving] = useState(false);
  useEffect(() => { interventions.owners().then(setOwners).catch(() => setOwners([])); }, []);

  const save = async () => {
    if (!student) return;
    setSaving(true);
    try { await interventions.create({ student: student.id, title: f.title, description: f.description, priority: f.priority, owner: f.owner || null, due_date: f.due_date || null }); toast.success('Intervention added.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title="New intervention">
      <div className="space-y-3">
        {student ? <p className="text-sm">For <b>{student.name}</b> <span className="text-slate-400">{student.student_id}</span> <button className="text-xs underline text-slate-500" onClick={() => setStudent(null)}>change</button></p>
          : <StudentPicker onPick={setStudent} label="Find the student" autoFocus />}
        <Field label="What needs doing"><input aria-label="Title" className={input} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Check in about attendance" /></Field>
        <Field label="Details"><textarea aria-label="Details" className={input} rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Priority"><select aria-label="Priority" className={input} value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value as 'normal' | 'high' })}><option value="normal">Normal</option><option value="high">High</option></select></Field>
          <Field label="Owner"><select aria-label="Owner" className={input} value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })}><option value="">Unassigned</option>{owners.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
          <Field label="Due"><input aria-label="Due date" type="date" className={input} min={todayStr()} value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !student || !f.title.trim()} onClick={save}>Add</button></div>
      </div>
    </Modal>
  );
}

function DetailDialog({ id, reviewer, onClose, onChanged }: { id: string; reviewer: boolean; onClose: () => void; onChanged: () => void }) {
  const { user } = useAuth();
  const [item, setItem] = useState<Intervention | null>(null);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [note, setNote] = useState('');
  const [closing, setClosing] = useState<null | 'done' | 'dismissed'>(null);
  const [closeNote, setCloseNote] = useState('');
  const [outcome, setOutcome] = useState<Outcome | ''>('');
  const [evidence, setEvidence] = useState('');

  const load = useCallback(() => { interventions.get(id).then(setItem).catch(() => onClose()); }, [id, onClose]);
  useEffect(load, [load]);
  useEffect(() => { if (reviewer) interventions.owners().then(setOwners).catch(() => setOwners([])); }, [reviewer]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast.success(ok); load(); onChanged(); } catch (e) { toast.error(errorText(e, 'That did not work.')); }
  };

  if (!item) return <Modal open onClose={onClose} title="Intervention"><Spinner /></Modal>;
  const active = item.status === 'open' || item.status === 'in_progress';
  const mine = Boolean(user && (user as { id?: string }).id && item.owner === (user as { id?: string }).id);
  const canWork = active && (reviewer || mine);

  return (
    <Modal open onClose={onClose} title={`${item.student_name}: ${item.title}`} size="lg">
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap gap-2">
          <Pill tone={statusTone(item.status)}>{STATUS_LABEL[item.status]}</Pill><Pill tone="slate">{SOURCE_LABEL[item.source]}</Pill>
          {item.priority === 'high' && <Pill tone="red">high priority</Pill>}{item.is_overdue && <Pill tone="red">overdue</Pill>}
          <span className="text-xs text-slate-500 ml-auto">{item.class_name} · opened {fmtDate(item.created_at)}{item.due_date && ` · due ${fmtDate(item.due_date)}`}</span>
        </div>
        {item.description && <p>{item.description}</p>}
        {item.suggested_actions.length > 0 && (
          <div><p className="font-bold mb-1">Suggested next steps</p><ul className="list-disc ml-5 text-slate-700">{item.suggested_actions.map((a) => <li key={a}>{a}</li>)}</ul></div>
        )}
        <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-50 px-3 py-2 md:grid-cols-4" aria-label="Record of support">
          <div><p className="text-xs text-slate-500">Support began</p><p className="font-semibold">{item.started_on ? fmtDate(item.started_on) : 'Not started'}</p></div>
          <div><p className="text-xs text-slate-500">Sessions delivered</p><p className="font-semibold">{item.sessions_delivered}</p></div>
          <div><p className="text-xs text-slate-500">Result</p><p className="font-semibold">{item.outcome ? OUTCOME_LABEL[item.outcome] : 'Not recorded'}</p></div>
          <div><p className="text-xs text-slate-500">Review on</p><p className="font-semibold">{item.review_on ? fmtDate(item.review_on) : 'Not set'}</p></div>
          {item.evidence && <p className="col-span-full"><span className="text-xs text-slate-500">Evidence: </span>{item.evidence}</p>}
        </div>
        {reviewer && active && (
          <div className="grid gap-2 md:grid-cols-4">
            <Field label="Review on"><input aria-label="Review date" type="date" className={input} value={item.review_on || ''} onChange={(e) => run(() => interventions.update(item.id, { review_on: e.target.value || null }), 'Review date set.')} /></Field>
          </div>
        )}
        {reviewer && active && (
          <div className="grid gap-2 md:grid-cols-3">
            <Field label="Owner"><select aria-label="Assign to" className={input} value={item.owner || ''} onChange={(e) => run(() => interventions.update(item.id, { owner: e.target.value || null }), 'Assigned.')}>
              <option value="">Unassigned</option>{owners.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
            <Field label="Due"><input aria-label="Change due date" type="date" className={input} value={item.due_date || ''} onChange={(e) => e.target.value && run(() => interventions.update(item.id, { due_date: e.target.value }), 'Due date changed.')} /></Field>
            <Field label="Priority"><select aria-label="Change priority" className={input} value={item.priority} onChange={(e) => run(() => interventions.update(item.id, { priority: e.target.value as 'normal' | 'high' }), 'Priority changed.')}><option value="normal">Normal</option><option value="high">High</option></select></Field>
          </div>
        )}

        <section aria-label="Notes">
          <p className="font-bold mb-1">Log</p>
          {item.notes.length === 0 ? <p className="text-slate-500">No notes yet.</p> : (
            <ul className="space-y-1.5">{item.notes.map((n) => <li key={n.id} className="rounded-lg bg-slate-50 px-3 py-2"><span className="text-xs text-slate-500">{n.author_name || 'System'} · {fmtDateTime(n.created_at)}</span><br />{n.text}</li>)}</ul>
          )}
          {canWork && (
            <div className="flex gap-2 mt-2">
              <input aria-label="Add a note" className={input} placeholder="Add a note" value={note} onChange={(e) => setNote(e.target.value)} />
              <button className={btn} disabled={!note.trim()} onClick={() => run(() => interventions.addNote(item.id, note).then(() => setNote('')), 'Note added.')}>Add</button>
            </div>
          )}
        </section>

        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-3">
          {canWork && item.status === 'open' && <button className={btnGhost} onClick={() => run(() => interventions.start(item.id), 'Started.')}>Start</button>}
          {canWork && <button className={btnGhost} onClick={() => run(() => interventions.logSession(item.id), 'Session counted.')}>Log a session</button>}
          {canWork && !closing && <button className={btn} onClick={() => setClosing('done')}>Mark done…</button>}
          {reviewer && active && !closing && <button className={btnGhost} onClick={() => setClosing('dismissed')}>Dismiss…</button>}
          {reviewer && !active && <button className={btnGhost} onClick={() => run(() => interventions.reopen(item.id), 'Reopened.')}>Reopen</button>}
          {closing && (
            <div className="w-full space-y-2">
              <textarea aria-label={closing === 'done' ? 'What was done' : 'Why no action is needed'} className={input} rows={2} value={closeNote} onChange={(e) => setCloseNote(e.target.value)}
                placeholder={closing === 'done' ? 'What was done?' : 'Why is no action needed?'} />
              {closing === 'done' && (
                <div className="grid gap-2 md:grid-cols-2">
                  <select aria-label="Result" className={input} value={outcome} onChange={(e) => setOutcome(e.target.value as Outcome | '')}>
                    <option value="">Result (optional)</option>{(Object.keys(OUTCOME_LABEL) as Outcome[]).map((k) => <option key={k} value={k}>{OUTCOME_LABEL[k]}</option>)}
                  </select>
                  <input aria-label="Evidence" className={input} placeholder="Evidence, e.g. absences before and after" value={evidence} onChange={(e) => setEvidence(e.target.value)} />
                </div>
              )}
              <div className="flex justify-end gap-2">
                <button className={btnGhost} onClick={() => setClosing(null)}>Cancel</button>
                <button className={closing === 'done' ? btn : btnDanger} disabled={!closeNote.trim()}
                  onClick={() => run(() => (closing === 'done' ? interventions.complete(item.id, closeNote, { outcome: outcome || undefined, evidence: evidence.trim() || undefined }) : interventions.dismiss(item.id, closeNote)), closing === 'done' ? 'Marked done.' : 'Dismissed.')}>
                  {closing === 'done' ? 'Mark done' : 'Dismiss'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
