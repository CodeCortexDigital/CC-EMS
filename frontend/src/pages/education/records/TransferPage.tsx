// Sending a 指導要録 to another school: 転学 (a copy of the whole record) or 進学 (the extract for the school the pupil advances to), kept as sent.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';
import recordTransfer, { errorText, TransferInfo, TransferKind, TransferRow } from '@/services/recordTransfer.service';
import security from '@/services/security.service';
import { wareki } from '@/utils/wareki';
import { btn, btnGhost, card, input, PageHead, Pill, Spinner } from '../hr/ui';
import RecordPrint from './RecordPrint';

const today = () => new Date().toISOString().slice(0, 10);

export default function TransferPage() {
  const { id = '' } = useParams();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [viewing, setViewing] = useState<TransferRow | null>(null);
  const [kind, setKind] = useState<TransferKind>('transfer');
  const [to, setTo] = useState('');
  const [sentOn, setSentOn] = useState(today());
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => recordTransfer.get(id).then(setInfo).catch((e) => setError(errorText(e, 'Could not load.')));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async () => {
    setBusy(true);
    try { const r = await recordTransfer.send(id, { kind, to_school: to, sent_on: sentOn, note }); toast.success('The record was sent and a copy was kept.'); setTo(''); setNote(''); setViewing(r); await load(); }
    catch (e) { toast.error(errorText(e, 'Could not send it.')); } finally { setBusy(false); }
  };
  const view = async (t: TransferRow) => { try { setViewing(await recordTransfer.issued(id, t.id)); } catch (e) { toast.error(errorText(e, 'Could not open it.')); } };
  const downloadJson = () => {
    if (!viewing?.snapshot) return;
    const href = URL.createObjectURL(new Blob([JSON.stringify(viewing.snapshot, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = href; a.download = `shido-yoroku-${viewing.kind}.json`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
  };

  if (error) return <div className="p-6"><p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p></div>;
  if (!info) return <div className="p-6"><Spinner /></div>;
  const r = info.retention;

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Send the record to another school (転学・進学)" hint="A copy of the 指導要録 for the school the pupil moves to. It can be sent once every year has the principal's seal.">
        <Link to={`/education/records/${id}`} className={btnGhost}>Back to the record</Link>
      </PageHead>

      <section className={card} aria-label="Retention">
        <h2 className="font-bold text-sm mb-1">How long the record is kept</h2>
        {!r.left_on ? <p className="text-sm text-slate-600">The pupil is still enrolled. The periods start when they leave: 20 years for the register (学籍に関する記録) and 5 years for the guidance part (指導に関する記録).</p> : (
          <ul className="text-sm text-slate-700 space-y-0.5">
            <li>Left on {wareki(r.left_on)}; counted from {wareki(r.counted_from)}.</li>
            <li>Guidance part (指導に関する記録): until {wareki(r.guidance_until)}{r.guidance_disposed_at ? ' (already disposed of)' : ''}.</li>
            <li>Register (学籍に関する記録): until {wareki(r.register_until)}.</li>
          </ul>
        )}
      </section>

      {!viewing && !info.ready && (
        <div role="alert" className={`${card} border-amber-300`}>
          <p className="text-sm font-semibold text-amber-900">It cannot be sent yet:</p>
          <ul className="list-disc pl-5 text-sm text-amber-900">{info.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      {!viewing && isAdmin && (
        <div className={`${card} grid gap-3 sm:grid-cols-2`}>
          <label className="block text-xs font-bold text-slate-600">Kind
            <select className={`${input} mt-1 font-normal`} value={kind} onChange={(e) => setKind(e.target.value as TransferKind)}>
              <option value="transfer">転学 (transfer: a copy of the whole record)</option>
              <option value="advance">進学 (advance: the extract for the next school)</option>
            </select></label>
          <label className="block text-xs font-bold text-slate-600">Send to (送付先)
            <input className={`${input} mt-1 font-normal`} value={to} onChange={(e) => setTo(e.target.value)} placeholder="School name" /></label>
          <label className="block text-xs font-bold text-slate-600">Date sent
            <input className={`${input} mt-1 font-normal`} type="date" value={sentOn} onChange={(e) => setSentOn(e.target.value)} /></label>
          <label className="block text-xs font-bold text-slate-600">Note
            <input className={`${input} mt-1 font-normal`} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <p className="sm:col-span-2 text-xs text-slate-500">A transfer sets the day the pupil left (which starts the retention periods). An advance records the next school.</p>
          <div><button className={btn} disabled={busy || !info.ready || !to.trim() || !sentOn} onClick={send}>Send it</button></div>
        </div>
      )}

      {info.transfers.length > 0 && (
        <div className={card}>
          <h2 className="font-bold text-sm mb-1">Sent so far</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {info.transfers.map((t) => <li key={t.id} className="py-1.5 flex flex-wrap items-center justify-between gap-2">
              <span>{t.kind_label} · {t.to_school} · {t.sent_on} · {t.issued_by}{t.note ? ` · ${t.note}` : ''}</span>
              <button className="text-xs font-semibold text-blue-600" onClick={() => view(t)}>View this copy</button></li>)}
          </ul>
        </div>
      )}

      {viewing?.snapshot && (
        <>
          <div className={`${card} flex flex-wrap items-center gap-3`}>
            <Pill tone="green">Sent copy</Pill><span className="text-sm">{viewing.kind_label} · {viewing.to_school} · {viewing.sent_on}</span>
            <button className={btnGhost} onClick={() => { security.logPrint('records', id); window.print(); }}>Print / PDF</button>
            <button className={btnGhost} onClick={downloadJson}>Download (JSON)</button>
            <button className={btnGhost} onClick={() => setViewing(null)}>Close</button>
          </div>
          <div className="record-print-root bg-white shadow print:shadow-none mx-auto max-w-[210mm] p-[10mm] print:p-0"><RecordPrint rec={viewing.snapshot} /></div>
        </>
      )}
    </div>
  );
}
