import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ShieldAlert, ShieldCheck, Trash2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import StudentPicker from '@/components/common/StudentPicker';
import { btn, btnDanger, btnGhost, card, Empty, errorText, Field, fmtDateTime, input, PageHead, Pill, Spinner } from '@/components/common/kit';
import { useAuth } from '@/hooks/useAuth';
import frontDesk, { PickupAdult, PickupGuardian, PickupList, Release, StudentHit } from '@/services/frontdesk.service';

type Target = PickupGuardian | PickupAdult;

export default function PickupPage() {
  const { role } = useAuth();
  const isAdmin = role === 'admin';
  const [student, setStudent] = useState<StudentHit | null>(null);
  const [list, setList] = useState<PickupList | null>(null);
  const [recent, setRecent] = useState<Release[]>([]);
  const [loading, setLoading] = useState(false);
  const [releasing, setReleasing] = useState<Target | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async (s: StudentHit) => {
    setLoading(true);
    try {
      const [l, r] = await Promise.all([frontDesk.pickupList(s.id), frontDesk.releases(s.id)]);
      setList(l); setRecent(r.slice(0, 5));
    } catch (e) { toast.error(errorText(e, 'Could not load this student.')); setList(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (student) load(student); }, [student, load]);

  const toggleBar = async (a: PickupAdult) => {
    if (!student) return;
    const next = !a.do_not_release;
    if (!window.confirm(next ? `Mark ${a.name} as DO NOT RELEASE?` : `Allow ${a.name} to collect this student again?`)) return;
    try { await frontDesk.updateAdult(a.id, { do_not_release: next }); load(student); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  const remove = async (a: PickupAdult) => {
    if (!student || !window.confirm(`Remove ${a.name} from the pickup list?`)) return;
    try { await frontDesk.removeAdult(a.id); load(student); } catch (e) { toast.error(errorText(e, 'Could not remove.')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Pickup" hint="Find the student, check who is allowed to collect them, and record who they leave with." />
      <div className={card}>
        <StudentPicker onPick={setStudent} label="Find the student" autoFocus />
      </div>

      {loading && <Spinner />}
      {!student && !loading && <Empty>Search for a student to see who may collect them.</Empty>}

      {student && list && !loading && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-black text-slate-900 mr-auto">{list.student.name} <span className="text-sm font-normal text-slate-400">{list.student.student_id}</span></h2>
            <button className={btn} onClick={() => setAdding(true)}><UserPlus className="inline w-3.5 h-3.5 mr-1" />Add an authorised adult</button>
          </div>

          <section className={card} aria-label="Guardians">
            <h3 className="font-bold text-sm mb-2">Parents and guardians</h3>
            {list.guardians.length === 0 ? <Empty>No guardians on file.</Empty> : (
              <ul className="divide-y divide-slate-100">
                {list.guardians.map((g) => (
                  <li key={g.id} className="py-2 flex flex-wrap items-center gap-3">
                    <div className="mr-auto">
                      <p className="font-semibold text-sm">{g.name} <span className="text-slate-400 font-normal">· {g.relationship}</span></p>
                      <p className="text-xs text-slate-500">{g.phone || 'No phone'}</p>
                      {g.custody_notes && <p className="text-xs text-amber-800 bg-amber-50 rounded px-2 py-1 mt-1 inline-block"><AlertTriangle className="inline w-3 h-3 mr-1" />{g.custody_notes}</p>}
                    </div>
                    {g.can_pickup ? <button className={btn} onClick={() => setReleasing(g)}>Release</button> : <Pill tone="red">Not allowed to collect</Pill>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={card} aria-label="Authorised adults">
            <h3 className="font-bold text-sm mb-2">Other authorised adults</h3>
            {list.authorized_adults.length === 0 ? <Empty>Nobody else is on the list.</Empty> : (
              <ul className="space-y-2">
                {list.authorized_adults.map((a) => (
                  <li key={a.id} className={`rounded-lg border p-3 ${a.do_not_release ? 'border-rose-400 bg-rose-50' : 'border-slate-200'}`}>
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="mr-auto">
                        <p className="font-semibold text-sm">{a.name} <span className="text-slate-400 font-normal">· {a.relationship || 'Authorised adult'}</span></p>
                        <p className="text-xs text-slate-500">{a.phone || 'No phone'} · {a.id_checked ? `ID on file${a.id_type ? ` (${a.id_type})` : ''}` : 'ID not yet checked'}</p>
                      </div>
                      {a.do_not_release && <Pill tone="red"><ShieldAlert className="w-3 h-3 mr-1" />DO NOT RELEASE</Pill>}
                      {!a.do_not_release && <button className={btn} onClick={() => setReleasing(a)}>Release</button>}
                      {a.do_not_release && isAdmin && <button className={btnDanger} onClick={() => setReleasing(a)}>Override…</button>}
                      <button className={btnGhost} onClick={() => toggleBar(a)}>{a.do_not_release ? 'Allow again' : 'Do not release'}</button>
                      <button aria-label={`Remove ${a.name}`} className="text-slate-400 hover:text-rose-600" onClick={() => remove(a)}><Trash2 className="w-4 h-4" /></button>
                    </div>
                    {a.do_not_release && (
                      <p className="text-sm text-rose-900 mt-2"><b>Do not let this person take the student.</b> {a.court_order_note || 'Ask an administrator.'}{!isAdmin && ' Only an administrator can override this.'}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={card} aria-label="Recent releases">
            <h3 className="font-bold text-sm mb-2">Recently released</h3>
            {recent.length === 0 ? <Empty>No releases recorded yet.</Empty> : (
              <ul className="divide-y divide-slate-100 text-sm">
                {recent.map((r) => (
                  <li key={r.id} className="py-1.5">
                    {fmtDateTime(r.released_at)} · to <b>{r.released_to_name}</b>{r.early_dismissal && ' · early dismissal'}{r.reason && ` · ${r.reason}`}
                    {r.override_used && <> <Pill tone="red">override</Pill></>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      {releasing && student && <ReleaseDialog student={student} target={releasing} onClose={() => setReleasing(null)} onDone={() => { setReleasing(null); load(student); }} />}
      {adding && student && <AdultDialog student={student} onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(student); }} />}
    </div>
  );
}

function ReleaseDialog({ student, target, onClose, onDone }: { student: StudentHit; target: Target; onClose: () => void; onDone: () => void }) {
  const barred = target.kind === 'adult' && target.do_not_release;
  const [idChecked, setIdChecked] = useState(false);
  const [reason, setReason] = useState('');
  const [early, setEarly] = useState(false);
  const [override, setOverride] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await frontDesk.release({
        student: student.id, id_confirmed: idChecked, reason, early_dismissal: early,
        ...(target.kind === 'adult' ? { authorized_adult: target.id } : { guardian: target.id }),
        ...(barred ? { override_reason: override } : {}),
      });
      toast.success(`${student.name} released to ${target.name}.`);
      onDone();
    } catch (e) { toast.error(errorText(e, 'Could not record the release.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title={`Release ${student.name} to ${target.name}`}>
      <div className="space-y-3">
        {barred && (
          <p className="text-sm rounded-lg bg-rose-50 border border-rose-300 text-rose-900 p-3" role="alert">
            <b>This person is marked DO NOT RELEASE.</b> Only continue if the court order has been lifted. Your reason is recorded in the activity log.
          </p>
        )}
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={idChecked} onChange={(e) => setIdChecked(e.target.checked)} />
          <span><ShieldCheck className="inline w-4 h-4 text-emerald-700 mr-1" />I have checked their photo ID.</span>
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={early} onChange={(e) => setEarly(e.target.checked)} />Early dismissal</label>
        <Field label="Reason (optional)"><input aria-label="Reason" className={input} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Dentist, family trip…" /></Field>
        {barred && <Field label="Why is this release allowed? (required)"><textarea aria-label="Override reason" className={input} rows={3} value={override} onChange={(e) => setOverride(e.target.value)} /></Field>}
        <div className="flex justify-end gap-2">
          <button className={btnGhost} onClick={onClose}>Cancel</button>
          <button className={barred ? btnDanger : btn} disabled={saving || !idChecked || (barred && !override.trim())} onClick={submit}>Release</button>
        </div>
      </div>
    </Modal>
  );
}

function AdultDialog({ student, onClose, onDone }: { student: StudentHit; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ name: '', relationship: '', phone: '', id_type: '', id_checked: false, do_not_release: false, court_order_note: '' });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try { await frontDesk.addAdult({ student: student.id, ...f }); toast.success('Added to the pickup list.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={`Authorised adult for ${student.name}`}>
      <div className="space-y-3">
        <Field label="Full name"><input aria-label="Adult name" className={input} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Relationship"><input aria-label="Relationship" className={input} value={f.relationship} onChange={(e) => setF({ ...f, relationship: e.target.value })} placeholder="Uncle, neighbour…" /></Field>
          <Field label="Phone"><input aria-label="Phone" className={input} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          <Field label="ID type"><input aria-label="ID type" className={input} value={f.id_type} onChange={(e) => setF({ ...f, id_type: e.target.value })} placeholder="Driver licence" /></Field>
          <label className="flex items-center gap-2 text-sm mt-6"><input type="checkbox" checked={f.id_checked} onChange={(e) => setF({ ...f, id_checked: e.target.checked })} />Photo ID seen</label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.do_not_release} onChange={(e) => setF({ ...f, do_not_release: e.target.checked })} />Do not release to this person</label>
        {f.do_not_release && <Field label="Court order or reason"><textarea aria-label="Court order note" className={input} rows={2} value={f.court_order_note} onChange={(e) => setF({ ...f, court_order_note: e.target.value })} /></Field>}
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !f.name.trim()} onClick={save}>Save</button></div>
      </div>
    </Modal>
  );
}
