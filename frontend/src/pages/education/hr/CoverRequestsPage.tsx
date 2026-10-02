import { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarPlus, CheckCircle2, Handshake, Undo2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import hr, { CoverCandidate, CoverRequest, errorText, PeriodChoices } from '@/services/hr.service';
import { btn, btnDanger, btnGhost, card, Empty, Field, fmtDate, input, PageHead, Pill, Spinner, StaffSelect, todayStr, useIsHr, useStaff } from './ui';

type Scope = 'involved' | 'mine' | 'covering' | 'all';

const statusPill = (r: CoverRequest) =>
  r.status === 'open' ? <Pill tone="amber">Needs cover</Pill>
    : r.status === 'filled' ? <Pill tone="green">Covered{r.substitute ? ` by ${r.substitute.name}` : ''}</Pill>
      : <Pill tone="slate">Cancelled</Pill>;

export default function CoverRequestsPage() {
  const isHr = useIsHr();
  const staff = useStaff();
  const [scope, setScope] = useState<Scope>(isHr ? 'all' : 'involved');
  const [rows, setRows] = useState<CoverRequest[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [assigning, setAssigning] = useState<CoverRequest | null>(null);

  const load = useCallback(() => {
    setRows(null);
    hr.cover.list({ scope, from: todayStr() }).then(setRows).catch(() => { setRows([]); toast.error('Could not load cover requests.'); });
  }, [scope]);
  useEffect(load, [load]);

  const act = async (r: CoverRequest, action: 'accept' | 'release' | 'cancel', ok: string) => {
    setBusy(r.id);
    try { await hr.cover.act(r.id, action); toast.success(ok); load(); } catch (e) { toast.error(errorText(e, 'That did not work.')); load(); }
    finally { setBusy(null); }
  };

  const grouped = useMemo(() => {
    const m = new Map<string, CoverRequest[]>();
    (rows || []).forEach((r) => m.set(r.date, [...(m.get(r.date) || []), r]));
    return [...m.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows]);

  const tabs: Array<[Scope, string]> = isHr
    ? [['all', 'Everything'], ['involved', 'Open to me'], ['mine', 'My requests'], ['covering', 'I am covering']]
    : [['involved', 'Open to me'], ['mine', 'My requests'], ['covering', 'I am covering']];

  return (
    <div className="p-4 sm:p-6">
      <PageHead title="Cover requests" hint="Ask for a period to be covered, or take one a colleague needs covered. Approved leave is covered automatically; this is for one-off absences, swaps and anything left over.">
        <button className={btn} onClick={() => setShowNew(true)}><CalendarPlus className="inline w-3.5 h-3.5 mr-1" />Request cover</button>
      </PageHead>

      <div className="flex flex-wrap gap-2 mb-4">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => setScope(k)} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${scope === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300 text-slate-700'}`}>{label}</button>
        ))}
      </div>

      {rows === null ? <Spinner /> : grouped.length === 0 ? (
        <Empty>{scope === 'involved' ? 'Nothing needs you right now. Periods you are free to cover will show up here.' : 'No cover requests from today onwards.'}</Empty>
      ) : (
        <div className="space-y-4">
          {grouped.map(([date, items]) => (
            <div key={date}>
              <p className="text-xs font-black text-slate-500 uppercase tracking-wide mb-1">{fmtDate(date)}</p>
              <div className="space-y-2">
                {items.map((r) => (
                  <div key={r.id} className={`${card} flex flex-wrap items-center gap-3`}>
                    <div className="mr-auto min-w-[14rem]">
                      <p className="font-bold text-sm">
                        {r.period ? `${r.period.name} (${r.period.start}-${r.period.end})` : 'Whole day'} · {r.description || [r.class_name, r.subject].filter(Boolean).join(' ')}
                      </p>
                      <p className="text-xs text-slate-500">{r.requester.name} is away{r.reason ? `: ${r.reason}` : ''}</p>
                    </div>
                    {statusPill(r)}
                    {r.can_accept && <button disabled={busy === r.id} className={btn} onClick={() => act(r, 'accept', 'You are covering this period.')}><CheckCircle2 className="inline w-3.5 h-3.5 mr-1" />I can cover</button>}
                    {isHr && r.status === 'open' && <button className={btnGhost} onClick={() => setAssigning(r)}><Handshake className="inline w-3.5 h-3.5 mr-1" />Assign</button>}
                    {r.status === 'filled' && (r.is_covering || isHr) && <button disabled={busy === r.id} className={btnGhost} onClick={() => act(r, 'release', 'Given back. It is open again.')}><Undo2 className="inline w-3.5 h-3.5 mr-1" />Give back</button>}
                    {r.can_cancel && r.status !== 'cancelled' && <button disabled={busy === r.id} className={btnDanger} onClick={() => act(r, 'cancel', 'Request cancelled.')}><XCircle className="inline w-3.5 h-3.5 mr-1" />Cancel</button>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {showNew && <NewRequest isHr={isHr} staff={staff} onClose={() => setShowNew(false)} onDone={() => { setShowNew(false); load(); }} />}
      {assigning && <AssignModal req={assigning} onClose={() => setAssigning(null)} onDone={() => { setAssigning(null); load(); }} />}
    </div>
  );
}

function NewRequest({ isHr, staff, onClose, onDone }: { isHr: boolean; staff: ReturnType<typeof useStaff>; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(todayStr());
  const [teacherId, setTeacherId] = useState('');
  const [choices, setChoices] = useState<PeriodChoices | null>(null);
  const [mode, setMode] = useState<'periods' | 'day' | 'duty'>('periods');
  const [picked, setPicked] = useState<string[]>([]);
  const [duty, setDuty] = useState({ period_id: '', description: '' });
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!date || (isHr && !teacherId)) { setChoices(null); return; }
    hr.cover.periods(date, isHr ? teacherId : undefined).then((c) => { setChoices(c); setPicked([]); }).catch(() => setChoices(null));
  }, [date, teacherId, isHr]);

  const submit = async () => {
    setSaving(true);
    try {
      const who = isHr ? { teacher_id: teacherId } : {};
      if (mode === 'day') {
        const r = await hr.cover.absence({ date, reason, ...who });
        toast.success(r.created.length ? `Cover asked for ${r.created.length} period(s).` : 'Those periods already have a request.');
      } else if (mode === 'duty') {
        await hr.cover.create({ date, reason, ...who, ...duty });
        toast.success('Cover requested.');
      } else {
        for (const id of picked) await hr.cover.create({ date, reason, entry_id: id, ...who });
        toast.success(`Cover requested for ${picked.length} period(s).`);
      }
      onDone();
    } catch (e) { toast.error(errorText(e, 'Could not request cover.')); } finally { setSaving(false); }
  };

  const ready = !!date && (!isHr || !!teacherId) && (mode === 'day' ? (choices?.entries.length ?? 0) > 0 : mode === 'duty' ? !!duty.period_id && !!duty.description.trim() : picked.length > 0);

  return (
    <Modal open onClose={onClose} title="Request cover" description="Colleagues who are free in that period are told straight away.">
      <div className="space-y-3">
        {isHr && <Field label="Who is away"><StaffSelect label="Who is away" staff={staff} value={teacherId} onChange={setTeacherId} /></Field>}
        <Field label="Date"><input aria-label="Date" type="date" min={todayStr()} className={input} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <div className="flex gap-2 text-xs font-bold">
          {([['periods', 'Choose periods'], ['day', 'Away all day'], ['duty', 'A duty or other period']] as const).map(([k, l]) => (
            <button key={k} onClick={() => setMode(k)} className={`px-3 py-1.5 rounded-full border ${mode === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{l}</button>
          ))}
        </div>
        {mode !== 'duty' && (
          choices === null ? <p className="text-xs text-slate-500">{isHr && !teacherId ? 'Choose who is away to see their periods.' : 'Loading periods…'}</p>
            : choices.entries.length === 0 ? <p className="text-sm text-amber-700">No timetabled periods that day.</p>
              : (
                <ul className="space-y-1">
                  {choices.entries.map((e) => (
                    <li key={e.id}>
                      <label className={`flex items-center gap-2 text-sm rounded-lg border px-3 py-2 ${e.already_requested ? 'opacity-50' : ''}`}>
                        <input type="checkbox" disabled={e.already_requested || mode === 'day'} checked={mode === 'day' ? !e.already_requested : picked.includes(e.id)}
                          onChange={(ev) => setPicked((p) => ev.target.checked ? [...p, e.id] : p.filter((x) => x !== e.id))} />
                        <span className="font-semibold">{e.period}</span><span className="text-slate-500">{e.time} · {e.label}</span>
                        {e.already_requested && <Pill tone="slate">already asked</Pill>}
                      </label>
                    </li>
                  ))}
                </ul>
              )
        )}
        {mode === 'duty' && (
          <>
            <Field label="Period">
              <select aria-label="Period" className={input} value={duty.period_id} onChange={(e) => setDuty({ ...duty, period_id: e.target.value })}>
                <option value="">Choose a period</option>
                {choices?.periods.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.time})</option>)}
              </select>
            </Field>
            <Field label="What needs covering"><input aria-label="What needs covering" className={input} placeholder="Lunch duty, bus supervision…" value={duty.description} onChange={(e) => setDuty({ ...duty, description: e.target.value })} /></Field>
          </>
        )}
        <Field label="Reason (optional)"><input aria-label="Reason" className={input} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="flex justify-end gap-2 pt-1">
          <button className={btnGhost} onClick={onClose}>Close</button>
          <button className={btn} disabled={!ready || saving} onClick={submit}>{saving ? 'Sending…' : 'Request cover'}</button>
        </div>
      </div>
    </Modal>
  );
}

function AssignModal({ req, onClose, onDone }: { req: CoverRequest; onClose: () => void; onDone: () => void }) {
  const [people, setPeople] = useState<CoverCandidate[] | null>(null);
  const [overriding, setOverriding] = useState<CoverCandidate | null>(null);
  const [reason, setReason] = useState('');
  useEffect(() => { hr.cover.candidates(req.id).then(setPeople).catch(() => setPeople([])); }, [req.id]);
  const pick = async (id: string, override_reason?: string) => {
    try { await hr.cover.act(req.id, 'assign', { teacher_id: id, override_reason }); toast.success('Cover assigned.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not assign.')); }
  };
  return (
    <Modal open onClose={onClose} title="Who covers?" description={`${fmtDate(req.date)} · ${req.period?.name || ''} · ${req.description || req.subject}. Only people who are free in that period are listed.`}>
      {people === null ? <Spinner /> : people.length === 0 ? <Empty>Nobody is free in that period.</Empty> : (
        <ul className="divide-y divide-slate-100">
          {people.map((p) => (
            <li key={p.id} className="py-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-semibold mr-auto">{p.name}</span>
                {p.qualified ? <Pill tone="green">qualified</Pill> : <Pill tone="amber">not qualified</Pill>}
                {p.relief && <Pill tone="blue">relief pool</Pill>}
                {p.qualified
                  ? <button className={btn} onClick={() => pick(p.id)}>Assign</button>
                  : <button className={btnGhost} onClick={() => { setOverriding(p); setReason(''); }}>Assign anyway…</button>}
              </div>
              {!p.qualified && p.reason && <p className="text-xs text-slate-500 mt-0.5">{p.reason}</p>}
              {overriding?.id === p.id && (
                <div className="mt-2 flex gap-2">
                  <input aria-label="Reason" className={input} placeholder="Why is this person covering? (recorded)" value={reason} onChange={(e) => setReason(e.target.value)} />
                  <button className={btn} disabled={!reason.trim()} onClick={() => pick(p.id, reason.trim())}>Confirm</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
