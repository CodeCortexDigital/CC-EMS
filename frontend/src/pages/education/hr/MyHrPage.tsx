import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import hr, { errorText, MyHr } from '@/services/hr.service';
import { card, Empty, fmtDate, PageHead, Pill, Spinner, todayStr } from './ui';

/** What HR holds about the signed-in staff member. Used as a page and inside the employee portal. */
export function MyHrPanel() {
  const [me, setMe] = useState<MyHr | null>(null);
  const load = useCallback(() => hr.me().then(setMe).catch(() => setMe({ linked: false })), []);
  useEffect(() => { load(); }, [load]);

  if (!me) return <Spinner />;
  if (!me.linked || !me.teacher) return <Empty>Your login is not linked to a staff record yet, so there is nothing to show. Ask the office to link it.</Empty>;

  const toggle = async (id: string, done: boolean) => { try { await hr.onboarding.toggle(id, done); load(); } catch (e) { toast.error(errorText(e, 'Could not update the task.')); } };
  const progress = async (id: string, value: number) => { try { await hr.goals.update(id, { progress: value, status: value >= 100 ? 'done' : 'open' }); load(); } catch (e) { toast.error(errorText(e, 'Could not update the goal.')); } };
  const todo = (me.onboarding || []).filter((t) => !t.done);
  const unread = (me.reviews || []).filter((r) => r.status === 'shared');

  return (
    <div className="space-y-4">
      <div className={card}>
        <p className="font-black text-lg">{me.teacher.name}</p>
        <p className="text-sm text-slate-500">{[me.teacher.role, me.teacher.department].filter(Boolean).join(' · ') || 'No role set'} · Reports to {me.teacher.manager?.name || 'nobody set'}</p>
      </div>

      {unread.length > 0 && (
        <Link to="/education/hr/performance" className="block rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm font-bold text-sky-900">
          {unread.length} review{unread.length > 1 ? 's' : ''} shared with you. Open Performance to read and acknowledge.
        </Link>
      )}

      {(me.onboarding || []).length > 0 && (
        <div className={card}>
          <h2 className="font-bold text-sm mb-2">Your onboarding checklist {todo.length === 0 && <Pill tone="green">all done</Pill>}</h2>
          <ul className="divide-y divide-slate-100">
            {(me.onboarding || []).map((t) => (
              <li key={t.id} className="py-1.5 flex items-center gap-2 text-sm">
                <input type="checkbox" aria-label={t.title} checked={t.done} onChange={() => toggle(t.id, !t.done)} />
                <span className={t.done ? 'line-through text-slate-400' : ''}>{t.title}</span>
                {t.due_date && !t.done && <span className={`ml-auto text-xs ${t.due_date < todayStr() ? 'text-rose-600 font-bold' : 'text-slate-500'}`}>due {fmtDate(t.due_date)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div className={card}>
          <h2 className="font-bold text-sm mb-2">Contract</h2>
          {(me.contracts || []).length === 0 ? <p className="text-sm text-slate-500">Nothing recorded.</p> : (me.contracts || []).map((c) => (
            <p key={c.id} className="text-sm">{c.kind.replace('_', ' ')} · from {fmtDate(c.start_date)} · {c.end_date ? `ends ${fmtDate(c.end_date)}` : 'open-ended'}{c.probation_end && c.probation_end >= todayStr() ? ` · probation ends ${fmtDate(c.probation_end)}` : ''}</p>
          ))}
        </div>
        <div className={card}>
          <h2 className="font-bold text-sm mb-2">Licences & certificates</h2>
          {(me.credentials || []).length === 0 ? <p className="text-sm text-slate-500">Nothing recorded.</p> : (
            <ul className="space-y-1">{(me.credentials || []).map((c) => (
              <li key={c.id} className="text-sm flex items-center gap-2"><span className="mr-auto">{c.name}</span>
                {c.expires_on ? <Pill tone={c.expires_on < todayStr() ? 'red' : 'slate'}>{c.expires_on < todayStr() ? 'expired' : 'expires'} {fmtDate(c.expires_on)}</Pill> : <Pill tone="slate">no expiry</Pill>}</li>
            ))}</ul>
          )}
        </div>
      </div>

      <div className={card}>
        <h2 className="font-bold text-sm mb-2">My goals</h2>
        {(me.goals || []).length === 0 ? <p className="text-sm text-slate-500">No goals set.</p> : (me.goals || []).map((g) => (
          <div key={g.id} className="py-2 border-b border-slate-100 last:border-0">
            <div className="flex items-center gap-2 text-sm"><span className="font-semibold mr-auto">{g.title}</span>{g.due_date && <span className="text-xs text-slate-500">due {fmtDate(g.due_date)}</span>}<Pill tone={g.status === 'done' ? 'green' : 'blue'}>{g.progress}%</Pill></div>
            {g.status === 'open' && <input aria-label={`Progress on ${g.title}`} type="range" min={0} max={100} step={5} defaultValue={g.progress} className="w-full accent-emerald-600" onMouseUp={(e) => progress(g.id, Number((e.target as HTMLInputElement).value))} onKeyUp={(e) => progress(g.id, Number((e.target as HTMLInputElement).value))} onTouchEnd={(e) => progress(g.id, Number((e.target as HTMLInputElement).value))} />}
          </div>
        ))}
      </div>

      <div className={card}>
        <div className="flex items-center mb-2"><h2 className="font-bold text-sm mr-auto">My cover requests and cover I am giving</h2><Link className="text-xs font-bold text-emerald-700" to="/education/hr/cover">Open cover requests</Link></div>
        {(me.cover || []).length === 0 ? <p className="text-sm text-slate-500">None coming up.</p> : (
          <ul className="divide-y divide-slate-100">{(me.cover || []).map((r) => (
            <li key={r.id} className="py-1.5 text-sm flex flex-wrap gap-2"><span className="font-semibold">{fmtDate(r.date)}</span><span>{r.period?.name} · {r.description || r.subject}</span>
              <span className="ml-auto text-slate-500">{r.is_covering ? 'You are covering' : r.status === 'filled' ? `Covered by ${r.substitute?.name}` : 'Waiting for someone'}</span></li>
          ))}</ul>
        )}
      </div>
    </div>
  );
}

export default function MyHrPage() {
  return (
    <div className="p-4 sm:p-6">
      <PageHead title="My HR" hint="Your contract, credentials, goals, onboarding and cover in one place." />
      <MyHrPanel />
    </div>
  );
}
