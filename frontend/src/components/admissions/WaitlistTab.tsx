import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDateTime, input, Pill, Spinner } from '@/components/common/kit';
import admissionService, { type Application } from '@/services/admission.service';
import extras, { Offer, WaitlistConfig, WaitlistEntry } from '@/services/admissionsExtras.service';

const WAITABLE = ['pending', 'reviewing', 'approved', 'waitlisted'];

export default function WaitlistTab({ defaultYear }: { defaultYear: string }) {
  const [configs, setConfigs] = useState<WaitlistConfig[] | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [editing, setEditing] = useState<WaitlistConfig | 'new' | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    extras.configs().then(setConfigs).catch(() => setConfigs([]));
    extras.offers().then(setOffers).catch(() => setOffers([]));
  }, []);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(errorText(e, 'That did not work.')); } };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <p className="text-sm text-slate-500 mr-auto max-w-2xl">Set how many seats each grade has. When a seat is free, the family at the front of the waiting list is offered it, and the next family is offered it if they decline or run out of time.</p>
        <button className={btn} onClick={() => setEditing('new')}><Plus className="inline w-3.5 h-3.5 mr-1" />Set seats for a grade</button>
      </div>

      {configs === null ? <Spinner /> : configs.length === 0 ? <Empty>No grades have seats set yet.</Empty> : (
        <ul className="space-y-2">
          {configs.map((c) => (
            <li key={c.id} className={card}>
              <div className="flex flex-wrap items-center gap-3">
                <button aria-label={open === c.id ? 'Hide the list' : 'Show the list'} onClick={() => setOpen(open === c.id ? null : c.id)} className="text-slate-500">
                  {open === c.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
                <b className="text-sm">{c.class_name} <span className="text-slate-400 font-normal">{c.academic_year}</span></b>
                <Pill tone={c.seats_left > 0 ? 'green' : 'slate'}>{c.seats_left} seat{c.seats_left === 1 ? '' : 's'} free</Pill>
                <span className="text-xs text-slate-500">{c.capacity} in total · {c.seats_taken} taken · {c.open_offers} offered · {c.waiting} waiting</span>
                <span className="ml-auto flex gap-2">
                  <button className={btnGhost} onClick={() => setEditing(c)}>Edit</button>
                  <button className={btnGhost} onClick={() => run(async () => { const r = await extras.fill(c.id); if (!r.offers_made) throw new Error('none'); }, 'Offers sent.')} title="Offer any free seats to the next families">Offer free seats</button>
                </span>
              </div>
              {open === c.id && <Entries config={c} onChanged={load} />}
            </li>
          ))}
        </ul>
      )}

      <section aria-label="Open offers">
        <h2 className="font-bold text-sm mb-2">Open offers {offers.length > 0 && <Pill tone="amber">{offers.length}</Pill>}</h2>
        {offers.length === 0 ? <Empty>No seats are currently on offer.</Empty> : (
          <ul className={`${card} divide-y divide-slate-100`}>
            {offers.map((o) => (
              <li key={o.id} className="py-2 flex flex-wrap items-center gap-3 text-sm">
                <b>{o.student_name}</b> <span className="text-slate-400">{o.application_no}</span>
                <span className="text-xs text-slate-500">answer by {fmtDateTime(o.expires_at)}</span>
                <button className={`${btnGhost} ml-auto`} onClick={() => window.confirm(`Take the offer back from ${o.student_name}?`) && run(() => extras.withdrawOffer(o.id), 'Offer withdrawn.')}>Withdraw</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {editing && <ConfigDialog initial={editing === 'new' ? null : editing} defaultYear={defaultYear} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function Entries({ config, onChanged }: { config: WaitlistConfig; onChanged: () => void }) {
  const [entries, setEntries] = useState<WaitlistEntry[] | null>(null);
  const [candidates, setCandidates] = useState<Application[]>([]);
  const [pick, setPick] = useState('');
  const [staffChild, setStaffChild] = useState(false);

  const load = useCallback(() => { extras.entries(config.id).then((r) => setEntries(r.entries)).catch(() => setEntries([])); }, [config.id]);
  useEffect(load, [load]);
  useEffect(() => {
    admissionService.list({ search: config.class_name, academic_year: config.academic_year })
      .then((r) => setCandidates((r.results || []).filter((a) => WAITABLE.includes(a.status) && a.applicant.applying_for_class.toLowerCase() === config.class_name.toLowerCase())))
      .catch(() => setCandidates([]));
  }, [config.class_name, config.academic_year, entries]);

  const onList = new Set((entries || []).map((e) => e.application));
  const addable = candidates.filter((a) => !onList.has(a.id) || false);

  const add = async () => {
    try { await extras.addToList(config.id, pick, staffChild); toast.success('Added to the waiting list.'); setPick(''); setStaffChild(false); load(); onChanged(); }
    catch (e) { toast.error(errorText(e, 'Could not add.')); }
  };

  return (
    <div className="mt-3 border-t border-slate-100 pt-3 space-y-3">
      {entries === null ? <Spinner /> : entries.length === 0 ? <p className="text-sm text-slate-500">Nobody is waiting for {config.class_name}.</p> : (
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-500"><th className="py-1 w-10">#</th><th>Child</th><th>Application</th><th>Priority</th><th /></tr></thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={e.id} className="border-t border-slate-100">
                <td className="py-1.5 font-bold">{i + 1}</td>
                <td className="font-semibold">{e.student_name}</td>
                <td className="text-slate-500">{e.application_no}</td>
                <td className="space-x-1">
                  {e.sibling && <Pill tone="blue">sibling</Pill>}
                  <label className="inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={e.staff_child} onChange={async (ev) => { await extras.setStaffChild(e.id, ev.target.checked).catch(() => undefined); load(); }} aria-label={`Staff child: ${e.student_name}`} />staff child</label>
                </td>
                <td className="text-right"><button aria-label={`Remove ${e.student_name}`} className="text-slate-400 hover:text-rose-600" onClick={async () => { await extras.removeEntry(e.id).catch(() => undefined); load(); onChanged(); }}><Trash2 className="w-4 h-4" /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Application to add" className={`${input} max-w-xs`} value={pick} onChange={(e) => setPick(e.target.value)}>
          <option value="">Add an application…</option>
          {addable.map((a) => <option key={a.id} value={a.id}>{a.applicant.full_name} · {a.application_no} · {a.status}</option>)}
        </select>
        <label className="inline-flex items-center gap-1.5 text-sm"><input type="checkbox" checked={staffChild} onChange={(e) => setStaffChild(e.target.checked)} />Staff child</label>
        <button className={btn} disabled={!pick} onClick={add}>Add to waiting list</button>
      </div>
    </div>
  );
}

function ConfigDialog({ initial, defaultYear, onClose, onSaved }: { initial: WaitlistConfig | null; defaultYear: string; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    class_name: initial?.class_name || '', academic_year: initial?.academic_year || defaultYear, capacity: String(initial?.capacity ?? ''),
    offer_hours: String(initial?.offer_hours ?? 72), sibling_priority: initial?.sibling_priority ?? true, staff_child_priority: initial?.staff_child_priority ?? true,
  });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await extras.saveConfig(initial?.id || null, { ...f, capacity: Number(f.capacity), offer_hours: Number(f.offer_hours) });
      toast.success('Saved.');
      onSaved();
    } catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={initial ? `${initial.class_name}: seats` : 'Seats for a grade'}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Grade (as families apply for it)"><input aria-label="Grade" className={input} value={f.class_name} disabled={!!initial} onChange={(e) => setF({ ...f, class_name: e.target.value })} placeholder="Grade 5" /></Field>
          <Field label="School year"><input aria-label="School year" className={input} value={f.academic_year} disabled={!!initial} onChange={(e) => setF({ ...f, academic_year: e.target.value })} placeholder="2026-2027" /></Field>
          <Field label="Seats in total"><input aria-label="Seats" type="number" min={0} className={input} value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></Field>
          <Field label="Hours to answer an offer"><input aria-label="Hours to answer" type="number" min={1} className={input} value={f.offer_hours} onChange={(e) => setF({ ...f, offer_hours: e.target.value })} /></Field>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.sibling_priority} onChange={(e) => setF({ ...f, sibling_priority: e.target.checked })} />Families with a child already at the school go first</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.staff_child_priority} onChange={(e) => setF({ ...f, staff_child_priority: e.target.checked })} />Staff children go next</label>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !f.class_name.trim() || !f.academic_year.trim() || f.capacity === ''} onClick={save}>Save</button></div>
      </div>
    </Modal>
  );
}
