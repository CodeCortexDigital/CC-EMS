import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Check, Plus, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import hr, { Candidate, errorText, OnboardingTask, Opening, Stage, STAGES } from '@/services/hr.service';
import { btn, btnDanger, btnGhost, card, Empty, Field, fmtDate, input, PageHead, Pill, Spinner, StaffSelect, todayStr, useIsHr, useStaff } from './ui';

const STAGE_LABEL: Record<Stage, string> = { applied: 'Applied', screening: 'Screening', interview: 'Interview', offer: 'Offer', hired: 'Hired', rejected: 'Not taken forward' };
const BOARD: Stage[] = ['applied', 'screening', 'interview', 'offer', 'hired'];

export default function RecruitmentPage() {
  const isHr = useIsHr();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'onboarding' ? 'onboarding' : 'pipeline';
  if (!isHr) return <p className="p-6 text-sm text-slate-500">Recruitment is open to administrators, HR and managers.</p>;
  return (
    <div className="p-4 sm:p-6">
      <PageHead title="Recruitment & onboarding" hint="Post a position, move candidates through interviews to an offer, hire them into the staff list and walk them through a first-weeks checklist.">
        <div className="flex gap-2">
          {([['pipeline', 'Hiring pipeline'], ['onboarding', 'Onboarding']] as const).map(([k, l]) => (
            <button key={k} onClick={() => setParams(k === 'pipeline' ? {} : { tab: k })} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${tab === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{l}</button>
          ))}
        </div>
      </PageHead>
      {tab === 'pipeline' ? <Pipeline /> : <Onboarding />}
    </div>
  );
}

function Pipeline() {
  const [openings, setOpenings] = useState<Opening[] | null>(null);
  const [sel, setSel] = useState<string>('');
  const [cands, setCands] = useState<Candidate[]>([]);
  const [showOpening, setShowOpening] = useState(false);
  const [showCand, setShowCand] = useState(false);
  const [open, setOpen] = useState<Candidate | null>(null);
  const [showRejected, setShowRejected] = useState(false);

  const loadOpenings = useCallback(() => hr.openings.list().then((o) => { setOpenings(o); setSel((s) => s || o[0]?.id || ''); }).catch(() => setOpenings([])), []);
  const loadCands = useCallback(() => (sel ? hr.candidates.list({ opening: sel }).then(setCands).catch(() => setCands([])) : setCands([])), [sel]);
  useEffect(() => { loadOpenings(); }, [loadOpenings]);
  useEffect(() => { loadCands(); }, [loadCands]);

  const current = openings?.find((o) => o.id === sel);
  const rejected = cands.filter((c) => c.stage === 'rejected');

  const setStatus = async (status: Opening['status']) => {
    if (!current) return;
    try { await hr.openings.update(current.id, { status }); loadOpenings(); } catch (e) { toast.error(errorText(e, 'Could not update the opening.')); }
  };

  if (openings === null) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {openings.map((o) => (
          <button key={o.id} onClick={() => setSel(o.id)} className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${sel === o.id ? 'bg-slate-900 text-white border-slate-900' : 'border-slate-300'}`}>
            {o.title} <span className="opacity-70">· {o.candidate_count}</span> {o.status !== 'open' && <span className="opacity-70">({o.status})</span>}
          </button>
        ))}
        <button className={btn} onClick={() => setShowOpening(true)}><Plus className="inline w-3.5 h-3.5 mr-1" />New opening</button>
      </div>

      {!current ? <Empty>No positions yet. Post your first opening to start collecting candidates.</Empty> : (
        <>
          <div className={`${card} flex flex-wrap items-center gap-3`}>
            <div className="mr-auto">
              <p className="font-black">{current.title}</p>
              <p className="text-xs text-slate-500">{[current.department, `${current.hired_count} of ${current.positions} filled`, current.closes_on ? `closes ${fmtDate(current.closes_on)}` : ''].filter(Boolean).join(' · ')}</p>
            </div>
            <Pill tone={current.status === 'open' ? 'green' : current.status === 'draft' ? 'amber' : 'slate'}>{current.status}</Pill>
            {current.status !== 'open' ? <button className={btnGhost} onClick={() => setStatus('open')}>Reopen</button> : <button className={btnGhost} onClick={() => setStatus('closed')}>Close position</button>}
            <button className={btn} onClick={() => setShowCand(true)}><UserPlus className="inline w-3.5 h-3.5 mr-1" />Add candidate</button>
          </div>

          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            {BOARD.map((st) => {
              const col = cands.filter((c) => c.stage === st);
              return (
                <div key={st} className="rounded-xl bg-slate-50 border border-slate-200 p-2 min-h-[8rem]">
                  <p className="text-xs font-black text-slate-500 uppercase mb-2">{STAGE_LABEL[st]} · {col.length}</p>
                  <div className="space-y-2">
                    {col.map((c) => (
                      <button key={c.id} onClick={() => setOpen(c)} className="w-full text-left bg-white rounded-lg border border-slate-200 px-3 py-2 hover:border-emerald-400">
                        <p className="font-bold text-sm">{c.full_name}</p>
                        <p className="text-xs text-slate-500">{c.rating ? `${'★'.repeat(c.rating)} ` : ''}{c.interview_at && c.stage === 'interview' ? `Interview ${new Date(c.interview_at).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : c.source}</p>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {rejected.length > 0 && (
            <div>
              <button className="text-xs font-bold text-slate-500" onClick={() => setShowRejected((v) => !v)}>{showRejected ? 'Hide' : 'Show'} {rejected.length} not taken forward</button>
              {showRejected && <div className="flex flex-wrap gap-2 mt-2">{rejected.map((c) => <button key={c.id} onClick={() => setOpen(c)} className="px-3 py-1 rounded-lg border border-slate-200 text-xs">{c.full_name}</button>)}</div>}
            </div>
          )}
        </>
      )}

      {showOpening && <OpeningForm onClose={() => setShowOpening(false)} onDone={(o) => { setShowOpening(false); setSel(o.id); loadOpenings(); }} />}
      {showCand && current && <CandidateForm opening={current} onClose={() => setShowCand(false)} onDone={() => { setShowCand(false); loadCands(); loadOpenings(); }} />}
      {open && <CandidateModal cand={open} onClose={() => setOpen(null)} onChanged={() => { loadCands(); loadOpenings(); }} />}
    </div>
  );
}

function OpeningForm({ onClose, onDone }: { onClose: () => void; onDone: (o: Opening) => void }) {
  const [f, setF] = useState({ title: '', department: '', positions: 1, description: '' });
  const save = async () => {
    try { onDone(await hr.openings.create({ ...f, status: 'open' })); toast.success('Position posted.'); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title="New opening">
      <div className="space-y-3">
        <Field label="Job title"><input aria-label="Job title" className={input} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Department"><input aria-label="Department" className={input} value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></Field>
          <Field label="Positions"><input aria-label="Positions" type="number" min={1} className={input} value={f.positions} onChange={(e) => setF({ ...f, positions: Math.max(1, Number(e.target.value) || 1) })} /></Field>
        </div>
        <Field label="Description"><textarea aria-label="Description" rows={3} className={input} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.title.trim()} onClick={save}>Post position</button></div>
      </div>
    </Modal>
  );
}

function CandidateForm({ opening, onClose, onDone }: { opening: Opening; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ full_name: '', email: '', phone: '', source: '' });
  const save = async () => {
    try { await hr.candidates.create({ ...f, opening: opening.id }); toast.success('Candidate added.'); onDone(); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title={`Add a candidate for ${opening.title}`}>
      <div className="space-y-3">
        <Field label="Full name"><input aria-label="Full name" className={input} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Email"><input aria-label="Email" type="email" className={input} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Phone"><input aria-label="Phone" className={input} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        </div>
        <Field label="Where did they hear of the job?"><input aria-label="Source" className={input} value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.full_name.trim()} onClick={save}>Add</button></div>
      </div>
    </Modal>
  );
}

function CandidateModal({ cand, onClose, onChanged }: { cand: Candidate; onClose: () => void; onChanged: () => void }) {
  const [c, setC] = useState(cand);
  const [note, setNote] = useState('');
  const [when, setWhen] = useState('');
  const [joining, setJoining] = useState(todayStr());
  const [email, setEmail] = useState(cand.email);
  const [saving, setSaving] = useState(false);
  const hired = c.stage === 'hired';

  const move = async (stage: Stage) => {
    setSaving(true);
    try { setC(await hr.candidates.stage(c.id, stage, note, stage === 'interview' && when ? new Date(when).toISOString() : undefined)); setNote(''); onChanged(); }
    catch (e) { toast.error(errorText(e, 'Could not move the candidate.')); } finally { setSaving(false); }
  };
  const rate = async (n: number) => { try { setC(await hr.candidates.update(c.id, { rating: n })); onChanged(); } catch { toast.error('Could not save the rating.'); } };
  const saveNotes = async () => { try { setC(await hr.candidates.update(c.id, { notes: c.notes })); toast.success('Notes saved.'); } catch { toast.error('Could not save the notes.'); } };
  const hire = async () => {
    setSaving(true);
    try {
      const r = await hr.candidates.hire(c.id, { joining_date: joining, email });
      toast.success(`${c.full_name} is now staff (${r.employee_id}) with a ${r.onboarding_tasks}-step onboarding checklist.`);
      onChanged(); onClose();
    } catch (e) { toast.error(errorText(e, 'Could not hire.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title={c.full_name} description={`${c.opening_title} · ${STAGE_LABEL[c.stage]}`} size="lg">
      <div className="space-y-4 text-sm">
        <p className="text-slate-600">{[c.email, c.phone, c.source].filter(Boolean).join(' · ') || 'No contact details yet.'}</p>
        <div className="flex items-center gap-1" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((n) => <button key={n} aria-label={`${n} star`} className={`text-xl ${c.rating && n <= c.rating ? 'text-amber-500' : 'text-slate-300'}`} onClick={() => rate(n)}>★</button>)}
        </div>
        {!hired && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-2">
            <p className="text-xs font-black text-slate-500 uppercase">Move to</p>
            <div className="flex flex-wrap gap-2">
              {STAGES.filter((s) => s !== 'hired' && s !== c.stage).map((s) => <button key={s} disabled={saving} className={s === 'rejected' ? btnDanger : btnGhost} onClick={() => move(s)}>{STAGE_LABEL[s]}</button>)}
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              <input aria-label="Interview time" type="datetime-local" className={input} value={when} onChange={(e) => setWhen(e.target.value)} />
              <input aria-label="Note for the history" className={input} placeholder="Note for the history (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <p className="text-xs text-slate-500">Set the interview time first if you are moving to Interview.</p>
          </div>
        )}
        {!hired && c.stage === 'offer' && (
          <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 space-y-2">
            <p className="font-bold">Hire {c.full_name}</p>
            <div className="grid sm:grid-cols-2 gap-2">
              <Field label="Start date"><input aria-label="Start date" type="date" className={input} value={joining} onChange={(e) => setJoining(e.target.value)} /></Field>
              <Field label="Email for their login"><input aria-label="Login email" type="email" className={input} value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            </div>
            <button className={btn} disabled={saving || !email.trim()} onClick={hire}><Check className="inline w-3.5 h-3.5 mr-1" />Hire and start onboarding</button>
          </div>
        )}
        <Field label="Notes"><textarea aria-label="Notes" rows={3} className={input} value={c.notes} onChange={(e) => setC({ ...c, notes: e.target.value })} onBlur={saveNotes} /></Field>
        <div>
          <p className="text-xs font-black text-slate-500 uppercase mb-1">History</p>
          <ul className="space-y-1 text-xs text-slate-600">
            {[...c.history].reverse().map((h, i) => <li key={i}>{new Date(h.at).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })} · {h.from ? `${STAGE_LABEL[h.from as Stage]} → ` : ''}{STAGE_LABEL[h.to as Stage] || h.to}{h.note ? ` · ${h.note}` : ''}{h.by ? ` (${h.by})` : ''}</li>)}
          </ul>
        </div>
      </div>
    </Modal>
  );
}

function Onboarding() {
  const staff = useStaff();
  const [tasks, setTasks] = useState<OnboardingTask[] | null>(null);
  const [teacher, setTeacher] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const load = useCallback(() => hr.onboarding.list().then(setTasks).catch(() => setTasks([])), []);
  useEffect(() => { load(); }, [load]);

  const byPerson = useMemo(() => {
    const m = new Map<string, { name: string; tasks: OnboardingTask[] }>();
    (tasks || []).forEach((t) => { const e = m.get(t.teacher) || { name: t.teacher_name, tasks: [] }; e.tasks.push(t); m.set(t.teacher, e); });
    return [...m.entries()];
  }, [tasks]);

  const toggle = async (t: OnboardingTask) => { try { await hr.onboarding.toggle(t.id, !t.done); load(); } catch (e) { toast.error(errorText(e, 'Could not update the task.')); } };
  const start = async () => {
    try { const r = await hr.onboarding.start(teacher); toast.success(r.created ? 'Checklist created.' : 'They already have a checklist.'); setTeacher(''); load(); }
    catch (e) { toast.error(errorText(e, 'Could not start onboarding.')); }
  };
  const addTask = async (teacherId: string) => {
    if (!newTitle.trim()) return;
    try { await hr.onboarding.add({ teacher: teacherId, title: newTitle.trim(), order: 99 }); setNewTitle(''); load(); } catch (e) { toast.error(errorText(e, 'Could not add the task.')); }
  };

  return (
    <div className="space-y-4">
      <div className={`${card} flex flex-wrap items-end gap-3`}>
        <div className="flex-1 min-w-[14rem]"><Field label="Start a checklist for an existing staff member"><StaffSelect label="Staff member" staff={staff} value={teacher} onChange={setTeacher} /></Field></div>
        <button className={btn} disabled={!teacher} onClick={start}>Create checklist</button>
        <p className="text-xs text-slate-500 w-full">Hiring someone from the pipeline creates their checklist automatically.</p>
      </div>
      {tasks === null ? <Spinner /> : byPerson.length === 0 ? <Empty>Nobody is onboarding right now.</Empty> : byPerson.map(([id, p]) => {
        const done = p.tasks.filter((t) => t.done).length;
        return (
          <div key={id} className={card}>
            <div className="flex items-center gap-3 mb-2">
              <p className="font-black mr-auto">{p.name}</p>
              <Pill tone={done === p.tasks.length ? 'green' : 'amber'}>{done} of {p.tasks.length} done</Pill>
            </div>
            <div className="h-1.5 rounded bg-slate-100 mb-2"><div className="h-1.5 rounded bg-emerald-500" style={{ width: `${(done / p.tasks.length) * 100}%` }} /></div>
            <ul className="divide-y divide-slate-100">
              {p.tasks.map((t) => (
                <li key={t.id} className="py-1.5 flex items-center gap-2 text-sm">
                  <input type="checkbox" aria-label={t.title} checked={t.done} onChange={() => toggle(t)} />
                  <span className={t.done ? 'line-through text-slate-400' : ''}>{t.title}</span>
                  {t.due_date && !t.done && <span className={`ml-auto text-xs ${t.due_date < todayStr() ? 'text-rose-600 font-bold' : 'text-slate-500'}`}>due {fmtDate(t.due_date)}</span>}
                </li>
              ))}
            </ul>
            <div className="flex gap-2 mt-2">
              <input aria-label={`Add a task for ${p.name}`} className={input} placeholder="Add another step" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
              <button className={btnGhost} onClick={() => addTask(id)}>Add</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
