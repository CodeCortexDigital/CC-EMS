// 指導要録 retention (administrators): which records have passed their 5 years (guidance part) or 20 years (register) and may be disposed of.
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import recordTransfer, { errorText, RetentionList, RetentionRow } from '@/services/recordTransfer.service';
import { wareki } from '@/utils/wareki';
import { btnDanger, btnGhost, card, Empty, PageHead, Spinner } from '../hr/ui';

export default function RetentionPage() {
  const [data, setData] = useState<RetentionList | null>(null);
  const load = () => recordTransfer.retention().then(setData).catch((e) => { setData({ guidance_years: 5, register_years: 20, guidance_due: [], register_due: [], soon: [], kept: 0 }); toast.error(errorText(e, 'Could not load.')); });
  useEffect(() => { load(); }, []);
  if (!data) return <div className="p-6"><Spinner /></div>;
  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Record retention (保存期間)" hint={`The register (学籍に関する記録) is kept ${data.register_years} years and the guidance part (指導に関する記録) ${data.guidance_years} years. Nothing is removed on its own: you choose what to dispose of, and only after its period.`}>
        <Link className={btnGhost} to="/education/records">Back</Link>
      </PageHead>
      <Due title={`Guidance part: past ${data.guidance_years} years`} part="guidance" rows={data.guidance_due} until="guidance_until" onDone={load}
        help="Disposing clears the ratings, comments and attendance of every year. The register part (class, teacher, seals) stays." />
      <Due title={`Register: past ${data.register_years} years`} part="register" rows={data.register_due} until="register_until" onDone={load}
        help="Disposing deletes the whole record. This cannot be undone." />
      <section className={card} aria-label="Reaching the end of the period soon">
        <h2 className="font-bold text-sm mb-1">Reaching the end of a period within a year</h2>
        {data.soon.length === 0 ? <Empty>None.</Empty> : (
          <ul className="text-sm divide-y divide-slate-100">
            {data.soon.map((r) => <li key={r.id} className="py-1.5">{r.student_number} · {r.class_name} · guidance until {wareki(r.guidance_until)} · register until {wareki(r.register_until)}</li>)}
          </ul>
        )}
      </section>
    </div>
  );
}

function Due({ title, part, rows, until, onDone, help }: { title: string; part: 'guidance' | 'register'; rows: RetentionRow[]; until: 'guidance_until' | 'register_until'; onDone: () => void; help: string }) {
  const [picked, setPicked] = useState<string[]>([]);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const go = async () => {
    setBusy(true);
    try { const r = await recordTransfer.dispose(part, picked); toast.success(`${r.disposed} record${r.disposed === 1 ? '' : 's'} disposed of.`); setPicked([]); setTyped(''); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not dispose of them.')); } finally { setBusy(false); }
  };
  return (
    <section className={card} aria-label={title}>
      <h2 className="font-bold text-sm mb-1">{title}</h2>
      <p className="text-xs text-slate-600 mb-2">{help}</p>
      {rows.length === 0 ? <Empty>None.</Empty> : (
        <>
          <ul className="text-sm divide-y divide-slate-100">
            {rows.map((r) => (
              <li key={r.id} className="py-1.5"><label className="flex items-center gap-2">
                <input type="checkbox" checked={picked.includes(r.id)} onChange={() => toggle(r.id)} aria-label={`Select ${r.student_number}`} />
                {r.student_number} · {r.class_name} · left {wareki(r.left_on)} · kept until {wareki(r[until])}</label></li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm w-48" inputMode="numeric" aria-label="Type the number of records to confirm" placeholder={`Type ${picked.length || 'the number'} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} />
            <button className={btnDanger} disabled={busy || picked.length === 0 || typed !== String(picked.length)} onClick={go}>Dispose of {picked.length || ''} selected</button>
          </div>
        </>
      )}
    </section>
  );
}
