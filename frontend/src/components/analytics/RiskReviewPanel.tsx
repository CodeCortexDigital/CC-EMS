// AI risk flags need a person. Each high or critical flag is listed with the reasons it was raised; staff confirm it, dismiss it or ask
// for more information, and the decision (who, when, why) is recorded. The score is advice: nothing is sent or changed because of it.
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/services/api';
import RiskModelCard from './RiskModelCard';

interface Review { decision: string; label: string; note: string; by: string; at: string | null }
interface Flag {
  student_id: string; student_name: string; student_roll: string; class_name: string | null; risk_level: string; risk_score: number;
  factors: Record<string, unknown>; fee_default_risk: number | null; dropout_risk: number | null; needs_review: boolean; review: Review | null;
}

const TONE: Record<string, string> = { critical: 'bg-rose-100 text-rose-800', high: 'bg-amber-100 text-amber-800' };
const reasons = (f: Record<string, unknown>) => ['dropout_alert', 'finance', 'attendance', 'academic'].map((k) => f[k]).filter((v): v is string => typeof v === 'string');
const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;

export default function RiskReviewPanel() {
  const [flags, setFlags] = useState<Flag[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');
  const load = useCallback(async () => {
    try {
      const rows: Flag[] = (await api.get('/ai/student-predictions/')).data || [];
      setFlags(rows.filter((r) => r.risk_level === 'high' || r.risk_level === 'critical'));
    } catch { setFlags([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const decide = async (f: Flag, decision: 'confirmed' | 'dismissed' | 'needs_info') => {
    setBusy(f.student_id + decision);
    try {
      await api.post(`/ai/student-predictions/${f.student_id}/review/`, { decision, note: notes[f.student_id] || '' });
      toast.success('Your decision is recorded.');
      setNotes((n) => ({ ...n, [f.student_id]: '' }));
      await load();
    } catch (e) { toast.error(errorText(e, 'Could not save your decision.')); } finally { setBusy(''); }
  };

  const waiting = (flags || []).filter((f) => f.needs_review).length;
  return (
    <section aria-label="Review AI risk flags" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="flex items-center gap-2 font-bold text-slate-800"><ShieldCheck size={16} /> Review AI risk flags {waiting > 0 && <span className="rounded-full bg-amber-100 px-2 text-xs text-amber-800">{waiting} waiting for a person</span>}</h3>
      <p className="mt-1 text-xs text-slate-500 max-w-3xl">
        These scores are advice for staff, worked out from attendance, marks, fees and behaviour. They are not used to decide anything about a student on their own,
        and nothing is sent or changed because of a score. A person looks at each high flag and records what they decided and why. If a later scan moves a
        student to a different level, the earlier review no longer applies and the flag comes back here.
      </p>
      <RiskModelCard />
      {flags === null ? <Loader2 className="mt-3 animate-spin text-slate-400" /> : flags.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No student is flagged high or critical. Run the AI risk scan to refresh the scores.</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100">
          {flags.map((f) => (
            <li key={f.student_id} className="py-3 text-sm" data-testid="risk-flag">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-slate-800">{f.student_name}</span>
                <span className="text-xs text-slate-500">{f.student_roll}{f.class_name ? ` · ${f.class_name}` : ''}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${TONE[f.risk_level]}`}>{f.risk_level === 'critical' ? 'Critical' : 'High'} · {Math.round(f.risk_score)}%</span>
                <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">Advice only</span>
              </div>
              {reasons(f.factors).length > 0 && <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">{reasons(f.factors).map((t) => <li key={t}>{t}</li>)}</ul>}
              {f.review ? (
                <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-600">
                  <CheckCircle2 size={14} className="mt-0.5 text-emerald-600" />
                  <span><b>{f.review.label}</b> by {f.review.by || 'staff'}{f.review.at ? `, ${new Date(f.review.at).toLocaleDateString(undefined, { dateStyle: 'medium' } as any)}` : ''}{f.review.note ? `. "${f.review.note}"` : ''}</span>
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <input aria-label={`Reason for ${f.student_name}`} className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs" placeholder={f.review ? 'Change your decision (reason)' : 'Reason (needed to dismiss or ask for more information)'}
                  value={notes[f.student_id] || ''} onChange={(e) => setNotes({ ...notes, [f.student_id]: e.target.value })} />
                <button onClick={() => decide(f, 'confirmed')} disabled={!!busy} className="rounded-lg border border-emerald-300 px-3 py-1.5 text-xs font-semibold text-emerald-700 disabled:opacity-50">Worth acting on</button>
                <button onClick={() => decide(f, 'needs_info')} disabled={!!busy || (notes[f.student_id] || '').trim().length < 5} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50">Need more information</button>
                <button onClick={() => decide(f, 'dismissed')} disabled={!!busy || (notes[f.student_id] || '').trim().length < 5} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50">Not a concern</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
