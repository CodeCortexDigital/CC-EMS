import { useEffect, useState } from 'react';
import { Download, Eye, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import security, { AccessReview } from '@/services/security.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm';
const input = 'rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white';
const PERIODS = [7, 30, 90, 365];

/** Security & privacy → Access review: who opened student records, exported or printed them, over a chosen period, for the regular review. */
export default function AccessReviewPanel() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<AccessReview | null>(null);
  useEffect(() => { setData(null); security.accessReview(days).then(setData).catch(() => { setData({ days, since: '', results: [], totals: { views: 0, exports: 0, prints: 0, refused: 0 } }); toast.error('Could not load the access review.'); }); }, [days]);

  return (
    <section className={`${card} p-5`} aria-labelledby="access-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="access-title" className="flex items-center gap-2 font-bold text-slate-800"><Eye size={16} /> Access to student records</h2>
        <div className="flex gap-2">
          <select className={input} aria-label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {PERIODS.map((p) => <option key={p} value={p}>Last {p} days</option>)}
          </select>
          <button type="button" className={`${input} inline-flex items-center gap-1 font-semibold`} onClick={() => security.exportAccessReview(days).catch(() => toast.error('Could not export.'))}><Download size={14} /> CSV</button>
        </div>
      </div>
      <p className="mt-1 text-sm text-slate-600">Who opened a student's record or the student list, who exported or printed records, and whose requests were refused. Review it regularly and follow up anything you do not expect. The same person opening the same record again within ten minutes counts once. Families looking at their own children are not listed.</p>
      {!data ? <div className="py-8 text-center"><Loader2 className="inline animate-spin text-slate-400" /></div> : data.results.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">Nothing recorded in this period.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500 border-b border-slate-100">
              <th className="py-2 pr-3 font-semibold">Person</th><th className="pr-3 font-semibold">Role</th><th className="pr-3 font-semibold">Records opened</th>
              <th className="pr-3 font-semibold">Different students</th><th className="pr-3 font-semibold">Exports</th><th className="pr-3 font-semibold">Prints</th>
              <th className="pr-3 font-semibold">Refused</th><th className="font-semibold">Last</th></tr></thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.user_id} className="border-b border-slate-50">
                  <td className="py-2 pr-3"><p className="font-semibold text-slate-800">{r.who}</p><p className="text-xs text-slate-500">{r.email}</p></td>
                  <td className="pr-3">{r.role}</td><td className="pr-3">{r.views}</td><td className="pr-3">{r.students_viewed}</td>
                  <td className="pr-3">{r.exports}</td><td className="pr-3">{r.prints}</td><td className="pr-3">{r.refused}</td><td className="text-xs text-slate-500">{r.last}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr className="text-xs font-semibold text-slate-600"><td className="pt-2" colSpan={2}>Total</td><td>{data.totals.views}</td><td /><td>{data.totals.exports}</td><td>{data.totals.prints}</td><td>{data.totals.refused}</td><td /></tr></tfoot>
          </table>
        </div>
      )}
    </section>
  );
}
