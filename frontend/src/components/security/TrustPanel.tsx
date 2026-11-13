import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, CircleDashed, Download, Loader2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import security, { AssessmentItem, SelfAssessment } from '@/services/security.service';
import TimestampPanel from './TimestampPanel';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-4';
const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;

const LABEL = { met: 'Met', partly: 'Partly', open: 'Open' } as const;
const TONE = { met: 'bg-emerald-100 text-emerald-800', partly: 'bg-amber-100 text-amber-800', open: 'bg-rose-100 text-rose-800' } as const;
const ICON = { met: CheckCircle2, partly: CircleDashed, open: XCircle } as const;

function Line({ item, busy, onAnswer }: { item: AssessmentItem; busy: boolean; onAnswer: (key: string, answer: 'yes' | 'partly' | 'no' | '', note: string) => void }) {
  const [note, setNote] = useState(item.source === 'school' && item.answer ? item.evidence : '');
  const Icon = ICON[item.status];
  return (
    <li className="py-3 flex gap-3">
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${item.status === 'met' ? 'text-emerald-600' : item.status === 'partly' ? 'text-amber-600' : 'text-rose-600'}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-800">{item.text}</p>
        {item.source === 'system' || item.answer ? <p className="text-xs text-slate-500 mt-0.5">{item.evidence}{item.answered_by ? ` (${item.answered_by})` : ''}</p> : null}
        {item.source === 'school' && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select aria-label={`Answer: ${item.text}`} className="rounded border border-slate-300 px-2 py-1 text-xs" disabled={busy} value={item.answer || ''}
              onChange={(e) => onAnswer(item.key, e.target.value as 'yes' | 'partly' | 'no' | '', note)}>
              <option value="">Not answered</option><option value="yes">Yes</option><option value="partly">Partly</option><option value="no">No</option>
            </select>
            <input aria-label={`Note: ${item.text}`} className="flex-1 min-w-[160px] rounded border border-slate-300 px-2 py-1 text-xs" placeholder="Note (who, when, where it is kept)" value={note}
              onChange={(e) => setNote(e.target.value)} onBlur={() => { if (item.answer && note !== item.evidence) onAnswer(item.key, item.answer as 'yes' | 'partly' | 'no', note); }} />
          </div>
        )}
      </div>
      <span className={`self-start rounded-full px-2 py-0.5 text-[11px] font-bold ${TONE[item.status]}`}>{LABEL[item.status]}</span>
    </li>
  );
}

/** Security & privacy → Trust & evidence: the self-assessment for the board, and the outside time stamps of the audit trail. */
export default function TrustPanel() {
  const [data, setData] = useState<SelfAssessment | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { security.selfAssessment().then(setData).catch(() => toast.error('Could not load the self-assessment.')); }, []);
  useEffect(load, [load]);

  const answer = async (key: string, value: 'yes' | 'partly' | 'no' | '', note: string) => {
    setBusy(true);
    try { setData(await security.answerAssessment(key, value, note)); } catch (e) { toast.error(errorText(e, 'Could not save the answer.')); } finally { setBusy(false); }
  };

  if (!data) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-slate-400" /></div>;
  const areas = Array.from(new Set(data.items.map((i) => i.area)));
  return (
    <div className="space-y-4">
      <section className={card} aria-label="Self-assessment">
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto">
            <h3 className="font-bold text-sm">Self-assessment for the board</h3>
            <p className="text-xs text-slate-600 mt-1 max-w-2xl">{data.disclaimer}</p>
          </div>
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={() => security.downloadAssessment().catch(() => toast.error('Could not download.'))}>
            <Download size={14} /> CSV
          </button>
        </div>
        <p className="mt-3 text-sm" aria-label="Summary">
          <b className="text-emerald-700">{data.summary.met}</b> met, <b className="text-amber-700">{data.summary.partly}</b> partly, <b className="text-rose-700">{data.summary.open}</b> open of {data.summary.total}.
        </p>
        {areas.map((area) => (
          <div key={area} className="mt-3">
            <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">{area}</h4>
            <ul className="divide-y divide-slate-100">
              {data.items.filter((i) => i.area === area).map((i) => <Line key={i.key} item={i} busy={busy} onAnswer={answer} />)}
            </ul>
          </div>
        ))}
      </section>
      <TimestampPanel />
    </div>
  );
}
