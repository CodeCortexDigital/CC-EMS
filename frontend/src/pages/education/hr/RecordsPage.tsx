import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import hr, { Alert, Contract, Credential, errorText } from '@/services/hr.service';
import { btn, btnGhost, card, Empty, Field, fmtDate, input, PageHead, Pill, Spinner, StaffSelect, todayStr, useIsHr, useStaff } from './ui';

const KINDS: Array<[string, string]> = [['full_time', 'Full time'], ['part_time', 'Part time'], ['fixed_term', 'Fixed term'], ['temporary', 'Temporary'], ['contractor', 'Contractor']];
const kindLabel = (k: string) => KINDS.find(([v]) => v === k)?.[1] || k;

/** Days between today and an ISO date (negative = already past). */
const daysUntil = (iso: string | null) => (iso ? Math.round((new Date(`${iso}T00:00:00`).getTime() - new Date(`${todayStr()}T00:00:00`).getTime()) / 86400000) : null);
const duePill = (iso: string | null) => {
  const d = daysUntil(iso);
  if (d === null) return <Pill tone="slate">no expiry</Pill>;
  if (d < 0) return <Pill tone="red">expired {-d} d ago</Pill>;
  if (d <= 30) return <Pill tone="amber">in {d} d</Pill>;
  return <Pill tone="green">{fmtDate(iso)}</Pill>;
};

export default function RecordsPage() {
  const isHr = useIsHr();
  const staff = useStaff();
  const [tab, setTab] = useState<'contracts' | 'credentials'>('contracts');
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [credentials, setCredentials] = useState<Credential[] | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [form, setForm] = useState<null | 'contract' | 'credential'>(null);

  const load = useCallback(() => {
    hr.contracts.list().then(setContracts).catch(() => setContracts([]));
    hr.credentials.list().then(setCredentials).catch(() => setCredentials([]));
    if (isHr) hr.alerts(60).then(setAlerts).catch(() => setAlerts([]));
  }, [isHr]);
  useEffect(load, [load]);

  const remove = async (kind: 'contract' | 'credential', id: string) => {
    if (!window.confirm('Delete this record?')) return;
    try { await (kind === 'contract' ? hr.contracts.remove(id) : hr.credentials.remove(id)); load(); } catch (e) { toast.error(errorText(e, 'Could not delete.')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Contracts & credentials" hint={isHr ? 'Keep each person’s contract, probation and licences current. Anything ending within 60 days is flagged.' : 'Your contract and credentials on file.'}>
        {isHr && <button className={btn} onClick={() => setForm(tab === 'contracts' ? 'contract' : 'credential')}><Plus className="inline w-3.5 h-3.5 mr-1" />Add {tab === 'contracts' ? 'contract' : 'credential'}</button>}
      </PageHead>

      {isHr && alerts.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">
          <p className="font-bold text-amber-900 mb-1">{alerts.length} need attention</p>
          <ul className="space-y-0.5">{alerts.slice(0, 6).map((a, i) => <li key={i}>{a.teacher_name} · {a.what} · {a.expired ? <b className="text-rose-700">ended {fmtDate(a.date)}</b> : <>ends {fmtDate(a.date)}</>}</li>)}</ul>
        </div>
      )}

      <div className="flex gap-2">
        {([['contracts', 'Contracts'], ['credentials', 'Licences & certificates']] as const).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${tab === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{l}</button>
        ))}
      </div>

      {tab === 'contracts' ? (contracts === null ? <Spinner /> : contracts.length === 0 ? <Empty>No contracts recorded.</Empty> : (
        <div className="space-y-2">
          {contracts.map((c) => (
            <div key={c.id} className={`${card} flex flex-wrap items-center gap-3`}>
              <div className="mr-auto"><p className="font-bold text-sm">{c.teacher_name}</p><p className="text-xs text-slate-500">{kindLabel(c.kind)} · from {fmtDate(c.start_date)}{c.notes ? ` · ${c.notes}` : ''}</p></div>
              {c.probation_end && daysUntil(c.probation_end)! >= 0 && <span className="text-xs text-slate-500">Probation ends {fmtDate(c.probation_end)}</span>}
              <span className="text-xs text-slate-500">{c.end_date ? 'Ends' : 'Open-ended'}</span>{c.end_date && duePill(c.end_date)}
              {isHr && <button aria-label="Delete contract" className="text-slate-400 hover:text-rose-600" onClick={() => remove('contract', c.id)}><Trash2 className="w-4 h-4" /></button>}
            </div>
          ))}
        </div>
      )) : (credentials === null ? <Spinner /> : credentials.length === 0 ? <Empty>No licences or certificates recorded.</Empty> : (
        <div className="space-y-2">
          {credentials.map((c) => (
            <div key={c.id} className={`${card} flex flex-wrap items-center gap-3`}>
              <div className="mr-auto"><p className="font-bold text-sm">{c.name}</p><p className="text-xs text-slate-500">{c.teacher_name}{c.issuer ? ` · ${c.issuer}` : ''}{c.number ? ` · #${c.number}` : ''}</p></div>
              <span className="text-xs text-slate-500">Expires</span>{duePill(c.expires_on)}
              {isHr && <button aria-label="Delete credential" className="text-slate-400 hover:text-rose-600" onClick={() => remove('credential', c.id)}><Trash2 className="w-4 h-4" /></button>}
            </div>
          ))}
        </div>
      ))}

      {form === 'contract' && <ContractForm staff={staff} onClose={() => setForm(null)} onDone={() => { setForm(null); load(); }} />}
      {form === 'credential' && <CredentialForm staff={staff} onClose={() => setForm(null)} onDone={() => { setForm(null); load(); }} />}
    </div>
  );
}

function ContractForm({ staff, onClose, onDone }: { staff: ReturnType<typeof useStaff>; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ teacher: '', kind: 'full_time', start_date: todayStr(), end_date: '', probation_end: '', notes: '' });
  const save = async () => {
    try { await hr.contracts.create({ ...f, end_date: f.end_date || null, probation_end: f.probation_end || null }); toast.success('Contract saved.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title="Add a contract">
      <div className="space-y-3">
        <Field label="Staff member"><StaffSelect label="Staff member" staff={staff} value={f.teacher} onChange={(v) => setF({ ...f, teacher: v })} /></Field>
        <Field label="Type"><select aria-label="Contract type" className={input} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Starts"><input aria-label="Starts" type="date" className={input} value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
          <Field label="Ends"><input aria-label="Ends" type="date" className={input} value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
          <Field label="Probation ends"><input aria-label="Probation ends" type="date" className={input} value={f.probation_end} onChange={(e) => setF({ ...f, probation_end: e.target.value })} /></Field>
        </div>
        <Field label="Notes"><input aria-label="Notes" className={input} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.teacher || !f.start_date} onClick={save}>Save</button></div>
      </div>
    </Modal>
  );
}

function CredentialForm({ staff, onClose, onDone }: { staff: ReturnType<typeof useStaff>; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ teacher: '', name: '', issuer: '', number: '', issued_on: '', expires_on: '' });
  const save = async () => {
    try { await hr.credentials.create({ ...f, issued_on: f.issued_on || null, expires_on: f.expires_on || null }); toast.success('Credential saved.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title="Add a licence or certificate">
      <div className="space-y-3">
        <Field label="Staff member"><StaffSelect label="Staff member" staff={staff} value={f.teacher} onChange={(v) => setF({ ...f, teacher: v })} /></Field>
        <Field label="Name"><input aria-label="Credential name" className={input} placeholder="State teaching licence, First aid, Background check…" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Issued by"><input aria-label="Issued by" className={input} value={f.issuer} onChange={(e) => setF({ ...f, issuer: e.target.value })} /></Field>
          <Field label="Number"><input aria-label="Number" className={input} value={f.number} onChange={(e) => setF({ ...f, number: e.target.value })} /></Field>
          <Field label="Issued on"><input aria-label="Issued on" type="date" className={input} value={f.issued_on} onChange={(e) => setF({ ...f, issued_on: e.target.value })} /></Field>
          <Field label="Expires on"><input aria-label="Expires on" type="date" className={input} value={f.expires_on} onChange={(e) => setF({ ...f, expires_on: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.teacher || !f.name.trim()} onClick={save}>Save</button></div>
      </div>
    </Modal>
  );
}
