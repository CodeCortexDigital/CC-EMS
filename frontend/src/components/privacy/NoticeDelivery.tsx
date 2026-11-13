import { useEffect, useState } from 'react';
import { Download, Loader2, MailCheck } from 'lucide-react';
import { toast } from 'sonner';
import privacy, { NoticeDeliveryData } from '@/services/privacy.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm';
const when = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' } as any);
const WHO: Array<['parents' | 'staff' | 'all', string]> = [['parents', 'Families'], ['staff', 'Staff'], ['all', 'Everyone']];

/** Security & privacy → Privacy → who has read the school's current notice, for following up with families who have not. */
export default function NoticeDelivery() {
  const [who, setWho] = useState<'parents' | 'staff' | 'all'>('parents');
  const [data, setData] = useState<NoticeDeliveryData | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(true);
  useEffect(() => { setData(null); privacy.noticeDelivery(who).then(setData).catch(() => { setData({ document: null, rows: [], summary: { people: 0, read: 0, not_read: 0 } }); toast.error('Could not load the delivery record.'); }); }, [who]);
  if (data && !data.document) return null;

  const rows = (data?.rows || []).filter((r) => !onlyUnread || !r.read);
  return (
    <section className={`${card} p-5`} aria-labelledby="delivery-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="delivery-title" className="flex items-center gap-2 font-bold text-slate-800"><MailCheck size={16} /> Who has read the notice</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" aria-label="Who" value={who} onChange={(e) => setWho(e.target.value as 'parents' | 'staff' | 'all')}>
            {WHO.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <label className="flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" checked={onlyUnread} onChange={(e) => setOnlyUnread(e.target.checked)} /> Only those who have not read it</label>
          <button type="button" className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold" onClick={() => privacy.noticeDeliveryCsv(who).catch(() => toast.error('Could not export.'))}><Download size={13} /> CSV</button>
        </div>
      </div>
      {!data ? <div className="py-6 text-center"><Loader2 className="inline animate-spin text-slate-400" /></div> : (
        <>
          <p className="mt-1 text-sm text-slate-600">{data.document?.title} (version {data.document?.version}): <b>{data.summary.read}</b> of {data.summary.people} have read it, <b>{data.summary.not_read}</b> have not. People are asked to read a new notice when they next sign in; this is the record of who has.</p>
          {rows.length === 0 ? <p className="py-4 text-center text-sm text-slate-500">{onlyUnread ? 'Everyone in this group has read it.' : 'Nobody in this group.'}</p> : (
            <div className="mt-2 max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white"><tr className="text-left text-xs text-slate-500 border-b border-slate-100"><th className="py-2 pr-3">Name</th><th className="pr-3">Email</th><th className="pr-3">Children</th><th>Read</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.user_id} className="border-b border-slate-50">
                      <td className="py-1.5 pr-3 font-semibold">{r.name}</td><td className="pr-3 text-slate-600">{r.email}</td><td className="pr-3 text-slate-600">{r.children}</td>
                      <td>{r.read ? <span className="text-emerald-700">{when(r.read_at as string)}</span> : <span className="text-amber-700">Not yet</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
