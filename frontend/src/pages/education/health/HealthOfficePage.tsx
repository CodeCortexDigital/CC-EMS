import { useCallback, useEffect, useState } from 'react';
import { Pill as PillIcon, Plus, Stethoscope } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import StudentPicker from '@/components/common/StudentPicker';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDateTime, input, nowLocal, PageHead, Pill, Spinner, Tabs, todayStr } from '@/components/common/kit';
import health, { ACTIONS, DOSE_STATUSES, HealthVisit, MedicationAuthorization, MedicationLog, ROUTES, VISIT_TYPES } from '@/services/health.service';
import type { StudentHit } from '@/services/frontdesk.service';

type Tab = 'visits' | 'medication';

export default function HealthOfficePage() {
  const [student, setStudent] = useState<StudentHit | null>(null);
  const [tab, setTab] = useState<Tab>('visits');

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Health office" hint="Record each visit and each dose of medicine. Parents are told about visits automatically. Health records are private to the nurse, administrators and the child's parents." />
      <div className={card}>
        <StudentPicker onPick={setStudent} label="Find a student" />
        {student && (
          <p className="text-sm mt-2">Working with <b>{student.name}</b> <span className="text-slate-400">{student.student_id}{student.class_name && ` · ${student.class_name}`}</span>{' '}
            <button className="text-xs underline text-slate-500" onClick={() => setStudent(null)}>show everyone</button></p>
        )}
      </div>
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[['visits', 'Visits'], ['medication', 'Medication']]} />
      {tab === 'visits' ? <VisitsTab student={student} /> : <MedicationTab student={student} />}
    </div>
  );
}

function VisitsTab({ student }: { student: StudentHit | null }) {
  const [rows, setRows] = useState<HealthVisit[] | null>(null);
  const [adding, setAdding] = useState(false);
  const load = useCallback(() => { setRows(null); health.visits(student?.id).then(setRows).catch(() => setRows([])); }, [student]);
  useEffect(load, [load]);

  return (
    <div className="space-y-3">
      <div className="flex"><button className={`${btn} ml-auto`} disabled={!student} title={student ? '' : 'Find a student first'} onClick={() => setAdding(true)}><Plus className="inline w-3.5 h-3.5 mr-1" />New visit</button></div>
      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>{student ? 'No visits recorded for this student.' : 'No visits recorded yet.'}</Empty> : (
        <ul className="space-y-2">
          {rows.map((v) => (
            <li key={v.id} className={card}>
              <div className="flex flex-wrap items-center gap-2">
                <Stethoscope className="w-4 h-4 text-emerald-700" />
                <b className="text-sm">{v.student_name}</b>
                <Pill tone="blue">{VISIT_TYPES.find(([k]) => k === v.visit_type)?.[1] || v.visit_type}</Pill>
                {v.sent_home && <Pill tone="amber">sent home</Pill>}
                {v.parent_notified_at && <Pill tone="green">parent told</Pill>}
                <span className="text-xs text-slate-400 ml-auto">{fmtDateTime(v.time_in)}{v.time_out && ` – ${fmtDateTime(v.time_out)}`}</span>
              </div>
              {v.complaint && <p className="text-sm mt-1">{v.complaint}</p>}
              <p className="text-xs text-slate-500 mt-1">{ACTIONS.find(([k]) => k === v.action_taken)?.[1]}{v.action_notes && ` · ${v.action_notes}`}{v.temperature && ` · ${v.temperature}°`}{v.recorded_by_name && ` · ${v.recorded_by_name}`}</p>
            </li>
          ))}
        </ul>
      )}
      {adding && student && <VisitDialog student={student} onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
    </div>
  );
}

function VisitDialog({ student, onClose, onDone }: { student: StudentHit; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ time_in: nowLocal(), time_out: '', visit_type: 'illness', complaint: '', action_taken: '', action_notes: '', sent_home: false, temperature: '' });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await health.addVisit({
        student: student.id, visit_type: f.visit_type, complaint: f.complaint, action_taken: f.action_taken, action_notes: f.action_notes,
        sent_home: f.sent_home || f.action_taken === 'sent_home', time_in: new Date(f.time_in).toISOString(),
        time_out: f.time_out ? new Date(f.time_out).toISOString() : null, temperature: f.temperature || null,
      });
      toast.success('Visit recorded.');
      onDone();
    } catch (e) { toast.error(errorText(e, 'Could not save the visit.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={`New visit: ${student.name}`}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Time in"><input aria-label="Time in" type="datetime-local" className={input} value={f.time_in} onChange={(e) => setF({ ...f, time_in: e.target.value })} /></Field>
          <Field label="Time out"><input aria-label="Time out" type="datetime-local" className={input} value={f.time_out} onChange={(e) => setF({ ...f, time_out: e.target.value })} /></Field>
          <Field label="Type"><select aria-label="Visit type" className={input} value={f.visit_type} onChange={(e) => setF({ ...f, visit_type: e.target.value })}>{VISIT_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="Temperature"><input aria-label="Temperature" className={input} inputMode="decimal" value={f.temperature} onChange={(e) => setF({ ...f, temperature: e.target.value })} /></Field>
        </div>
        <Field label="Complaint"><textarea aria-label="Complaint" className={input} rows={2} value={f.complaint} onChange={(e) => setF({ ...f, complaint: e.target.value })} /></Field>
        <Field label="Action taken"><select aria-label="Action taken" className={input} value={f.action_taken} onChange={(e) => setF({ ...f, action_taken: e.target.value })}>{ACTIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Notes"><input aria-label="Notes" className={input} value={f.action_notes} onChange={(e) => setF({ ...f, action_notes: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.sent_home} onChange={(e) => setF({ ...f, sent_home: e.target.checked })} />Sent home</label>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving} onClick={save}>Save visit</button></div>
      </div>
    </Modal>
  );
}

function MedicationTab({ student }: { student: StudentHit | null }) {
  const [rows, setRows] = useState<MedicationAuthorization[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [dosing, setDosing] = useState<MedicationAuthorization | null>(null);
  const load = useCallback(() => { setRows(null); health.authorizations(student?.id).then(setRows).catch(() => setRows([])); }, [student]);
  useEffect(load, [load]);

  const consent = async (a: MedicationAuthorization) => {
    try { await health.updateAuthorization(a.id, { parent_consent: true }); load(); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  const switchOff = async (a: MedicationAuthorization) => {
    if (!window.confirm(`Stop ${a.medication_name} for ${a.student_name}?`)) return;
    try { await health.updateAuthorization(a.id, { is_active: false }); load(); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };

  return (
    <div className="space-y-3">
      <div className="flex"><button className={`${btn} ml-auto`} disabled={!student} title={student ? '' : 'Find a student first'} onClick={() => setAdding(true)}><Plus className="inline w-3.5 h-3.5 mr-1" />Add medication</button></div>
      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>No medication permissions on file.</Empty> : (
        <ul className="space-y-2">
          {rows.map((a) => (
            <li key={a.id} className={card}>
              <div className="flex flex-wrap items-center gap-2">
                <PillIcon className="w-4 h-4 text-emerald-700" />
                <b className="text-sm">{a.medication_name}</b> <span className="text-sm text-slate-500">{a.dose} · {ROUTES.find(([k]) => k === a.route)?.[1]}{a.times && ` · ${a.times}`}</span>
                <span className="text-sm">for <b>{a.student_name}</b></span>
                {a.is_current ? <Pill tone="green">current</Pill> : !a.parent_consent ? <Pill tone="amber">waiting for parent consent</Pill> : !a.is_active ? <Pill tone="slate">stopped</Pill> : <Pill tone="red">outside its dates</Pill>}
                <span className="ml-auto flex gap-2">
                  {!a.parent_consent && <button className={btnGhost} onClick={() => consent(a)}>Consent received</button>}
                  {a.is_current && <button className={btn} onClick={() => setDosing(a)}>Give dose</button>}
                  {a.is_active && <button className={btnGhost} onClick={() => switchOff(a)}>Stop</button>}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">From {a.start_date}{a.end_date && ` to ${a.end_date}`}{a.min_hours_between_doses ? ` · at least ${a.min_hours_between_doses} h between doses` : ''}{a.instructions && ` · ${a.instructions}`}</p>
              <DoseHistory authorization={a.id} />
            </li>
          ))}
        </ul>
      )}
      {adding && student && <AuthorizationDialog student={student} onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
      {dosing && <DoseDialog authorization={dosing} onClose={() => setDosing(null)} onDone={() => { setDosing(null); load(); }} />}
    </div>
  );
}

function DoseHistory({ authorization }: { authorization: string }) {
  const [rows, setRows] = useState<MedicationLog[]>([]);
  useEffect(() => { health.doses(authorization).then((r) => setRows(r.slice(0, 3))).catch(() => setRows([])); }, [authorization]);
  if (rows.length === 0) return null;
  return (
    <ul className="mt-2 text-xs text-slate-600 border-t border-slate-100 pt-2" aria-label="Recent doses">
      {rows.map((d) => <li key={d.id}>{fmtDateTime(d.given_at)} · {d.status}{d.dose_given && ` · ${d.dose_given}`}{d.given_by_name && ` · ${d.given_by_name}`}{d.override_reason && <> · <Pill tone="amber">early: {d.override_reason}</Pill></>}</li>)}
    </ul>
  );
}

function AuthorizationDialog({ student, onClose, onDone }: { student: StudentHit; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ medication_name: '', dose: '', route: 'oral', times: '', min_hours_between_doses: '', start_date: todayStr(), end_date: '', instructions: '', prescriber: '', parent_consent: false });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await health.addAuthorization({ student: student.id, ...f, min_hours_between_doses: f.min_hours_between_doses ? Number(f.min_hours_between_doses) : null, end_date: f.end_date || null });
      toast.success('Medication added.');
      onDone();
    } catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal open onClose={onClose} title={`Medication for ${student.name}`}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Medicine"><input aria-label="Medicine" className={input} value={f.medication_name} onChange={set('medication_name')} /></Field>
          <Field label="Dose"><input aria-label="Dose" className={input} value={f.dose} onChange={set('dose')} placeholder="200 mg" /></Field>
          <Field label="Route"><select aria-label="Route" className={input} value={f.route} onChange={set('route')}>{ROUTES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="When"><input aria-label="When" className={input} value={f.times} onChange={set('times')} placeholder="12:00, with lunch" /></Field>
          <Field label="Starts"><input aria-label="Starts" type="date" className={input} value={f.start_date} onChange={set('start_date')} /></Field>
          <Field label="Ends"><input aria-label="Ends" type="date" className={input} value={f.end_date} onChange={set('end_date')} /></Field>
          <Field label="Hours between doses"><input aria-label="Hours between doses" className={input} inputMode="numeric" value={f.min_hours_between_doses} onChange={set('min_hours_between_doses')} /></Field>
          <Field label="Prescriber"><input aria-label="Prescriber" className={input} value={f.prescriber} onChange={set('prescriber')} /></Field>
        </div>
        <Field label="Instructions"><textarea aria-label="Instructions" className={input} rows={2} value={f.instructions} onChange={set('instructions')} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.parent_consent} onChange={(e) => setF({ ...f, parent_consent: e.target.checked })} />The parent has given written consent</label>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !f.medication_name.trim() || !f.dose.trim()} onClick={save}>Save</button></div>
      </div>
    </Modal>
  );
}

function DoseDialog({ authorization, onClose, onDone }: { authorization: MedicationAuthorization; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState('given');
  const [dose, setDose] = useState(authorization.dose);
  const [notes, setNotes] = useState('');
  const [override, setOverride] = useState('');
  const [tooSoon, setTooSoon] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await health.giveDose({ authorization: authorization.id, status, dose_given: dose, notes, ...(override.trim() ? { override_reason: override } : {}) });
      toast.success('Dose recorded.');
      onDone();
    } catch (e: any) {
      const reason = e?.response?.data?.override_reason;
      if (Array.isArray(reason) || typeof reason === 'string') setTooSoon(Array.isArray(reason) ? reason[0] : reason);   // too soon: ask for a reason, then try again
      else toast.error(errorText(e, 'Could not record the dose.'));
    } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title={`${authorization.medication_name} for ${authorization.student_name}`}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="What happened"><select aria-label="Dose status" className={input} value={status} onChange={(e) => setStatus(e.target.value)}>{DOSE_STATUSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="Dose given"><input aria-label="Dose given" className={input} value={dose} onChange={(e) => setDose(e.target.value)} /></Field>
        </div>
        <Field label="Notes"><input aria-label="Dose notes" className={input} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {tooSoon && (
          <div className="rounded-lg bg-amber-50 border border-amber-300 p-3 space-y-2" role="alert">
            <p className="text-sm text-amber-900"><b>Too soon.</b> {tooSoon}</p>
            <textarea aria-label="Reason for giving it early" className={input} rows={2} value={override} onChange={(e) => setOverride(e.target.value)} placeholder="Why is it being given early?" />
          </div>
        )}
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || (!!tooSoon && !override.trim())} onClick={save}>{tooSoon ? 'Give anyway' : 'Record dose'}</button></div>
      </div>
    </Modal>
  );
}
