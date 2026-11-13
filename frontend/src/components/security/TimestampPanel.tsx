import { useCallback, useEffect, useState } from 'react';
import { Download, Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import security, { TimestampState } from '@/services/security.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-4';
const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;
const when = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' } as any);

/** Security & privacy → Trust: the audit trail's hash, signed with the time by an outside authority, so history cannot be rewritten unnoticed. */
export default function TimestampPanel() {
  const [data, setData] = useState<TimestampState | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { security.timestamps().then(setData).catch(() => toast.error('Could not load the time stamps.')); }, []);
  useEffect(load, [load]);

  const stamp = async () => {
    setBusy(true);
    try { setData(await security.stampNow()); toast.success('Time-stamped.'); } catch (e) { toast.error(errorText(e, 'Could not time-stamp.')); } finally { setBusy(false); }
  };

  if (!data) return <div className={card}><Loader2 className="animate-spin text-slate-400" /></div>;
  return (
    <section className={card} aria-label="Outside time stamps">
      <h3 className="font-bold text-sm flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-700" />Outside time stamps for the audit trail</h3>
      <p className="text-xs text-slate-600 mt-1 leading-relaxed">
        Student records and AI decisions are kept for years. Each school's trail is chained so that a change shows up. To protect it against someone who rewrites the whole trail,
        the newest hash (a 64-character fingerprint, no names or data) is sent to an outside time-stamping authority, which signs it with the time. The signed reply is kept here.
        If history before that time is later changed, the check below fails.
      </p>
      {!data.enabled ? (
        <p className="mt-3 text-sm text-amber-800">No time-stamping authority is set up on the server yet (the setting TIMESTAMP_AUTHORITY_URL). Nothing has been sent anywhere.</p>
      ) : (
        <div className="mt-3 space-y-2 text-sm">
          <p className={data.chain.ok ? 'text-emerald-700 font-semibold' : 'text-rose-700 font-semibold'}>
            {data.chain.ok ? 'The trail checks out: nothing was changed, removed or inserted.' : 'The trail does not check out.'}
          </p>
          {data.chain.problems.map((p) => <p key={p} className="text-xs text-rose-700">{p}</p>)}
          <p className="text-slate-600">{data.records} records. Authority: <code className="text-xs">{data.authority}</code></p>
          <p className={data.up_to_date ? 'text-slate-600' : 'text-amber-800'}>
            {data.stamps.length === 0 ? 'Not time-stamped yet.' : data.up_to_date ? `The newest record is time-stamped (${when(data.stamps[0].at)}).` : `New records since the last time stamp (${when(data.stamps[0].at)}).`}
          </p>
          <button className="auth-primary-btn w-auto px-4 disabled:opacity-50" disabled={busy || data.up_to_date || data.records === 0} onClick={stamp}>
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} Time-stamp now
          </button>
          {data.stamps.length > 0 && (
            <div className="overflow-x-auto pt-2">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-slate-500 border-b border-slate-100"><th className="py-1 pr-3">When</th><th className="pr-3">Up to record</th><th className="pr-3">Hash</th><th /></tr></thead>
                <tbody>
                  {data.stamps.map((s) => (
                    <tr key={s.id} className="border-b border-slate-50">
                      <td className="py-1 pr-3 whitespace-nowrap">{when(s.at)}</td><td className="pr-3">{s.seq}</td><td className="pr-3"><code>{s.hash.slice(0, 16)}…</code></td>
                      <td><button className="inline-flex items-center gap-1 text-blue-600 font-semibold" onClick={() => security.downloadStamp(s.id, s.seq).catch(() => toast.error('Could not download.'))}><Download size={12} /> Signed reply</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[11px] text-slate-500 mt-2">To check a signed reply yourself: <code>{data.how_to_check}</code></p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
