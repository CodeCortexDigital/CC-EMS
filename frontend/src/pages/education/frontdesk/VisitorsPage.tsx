import { useCallback, useEffect, useState } from 'react';
import { LogOut, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDateTime, input, PageHead, Pill, Spinner, todayStr } from '@/components/common/kit';
import frontDesk, { Visitor, VisitorInput } from '@/services/frontdesk.service';

const BLANK: VisitorInput = { name: '', organisation: '', visiting: '', purpose: '', badge_number: '' };

export default function VisitorsPage() {
  const [onSite, setOnSite] = useState<Visitor[] | null>(null);
  const [today, setToday] = useState<Visitor[]>([]);
  const [form, setForm] = useState<VisitorInput>(BLANK);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    frontDesk.visitors({ on_site: true }).then(setOnSite).catch(() => setOnSite([]));
    frontDesk.visitors({ date_from: todayStr(), date_to: todayStr() }).then(setToday).catch(() => setToday([]));
  }, []);
  useEffect(load, [load]);

  const signIn = async () => {
    setSaving(true);
    try { await frontDesk.signIn(form); toast.success(`${form.name} signed in.`); setForm(BLANK); load(); }
    catch (e) { toast.error(errorText(e, 'Could not sign in.')); } finally { setSaving(false); }
  };
  const signOut = async (v: Visitor) => {
    try { await frontDesk.signOut(v.id); toast.success(`${v.name} signed out.`); load(); } catch (e) { toast.error(errorText(e, 'Could not sign out.')); }
  };
  const set = (k: keyof VisitorInput) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Visitors" hint="Sign visitors in and out. The list below is who is in the building right now.">
        <button className={btnGhost} onClick={() => window.print()}><Printer className="inline w-3.5 h-3.5 mr-1" />Print on-site list</button>
      </PageHead>

      <section className={`${card} print:hidden`} aria-label="Sign a visitor in">
        <h2 className="font-bold text-sm mb-3">Sign in</h2>
        <div className="grid gap-3 md:grid-cols-5">
          <Field label="Name"><input aria-label="Visitor name" className={input} value={form.name} onChange={set('name')} /></Field>
          <Field label="Organisation"><input aria-label="Organisation" className={input} value={form.organisation} onChange={set('organisation')} /></Field>
          <Field label="Visiting"><input aria-label="Visiting" className={input} value={form.visiting} onChange={set('visiting')} placeholder="Who or what" /></Field>
          <Field label="Purpose"><input aria-label="Purpose" className={input} value={form.purpose} onChange={set('purpose')} /></Field>
          <Field label="Badge number"><input aria-label="Badge number" className={input} value={form.badge_number} onChange={set('badge_number')} /></Field>
        </div>
        <div className="mt-3 flex justify-end"><button className={btn} disabled={saving || !(form.name || '').trim()} onClick={signIn}>Sign in</button></div>
      </section>

      <section className={card} aria-label="On site now">
        <h2 className="font-bold text-sm mb-2">On site now {onSite && <Pill tone={onSite.length ? 'amber' : 'slate'}>{onSite.length}</Pill>}</h2>
        {onSite === null ? <Spinner /> : onSite.length === 0 ? <Empty>No visitors in the building.</Empty> : (
          <ul className="divide-y divide-slate-100">
            {onSite.map((v) => (
              <li key={v.id} className="py-2 flex flex-wrap items-center gap-3">
                <div className="mr-auto">
                  <p className="font-semibold text-sm">{v.name}{v.organisation && <span className="text-slate-400 font-normal"> · {v.organisation}</span>}</p>
                  <p className="text-xs text-slate-500">In {fmtDateTime(v.checked_in_at)}{v.visiting && ` · visiting ${v.visiting}`}{v.purpose && ` · ${v.purpose}`}{v.badge_number && ` · badge ${v.badge_number}`}</p>
                </div>
                <button className={`${btnGhost} print:hidden`} onClick={() => signOut(v)}><LogOut className="inline w-3.5 h-3.5 mr-1" />Sign out</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={`${card} print:hidden`} aria-label="Today's log">
        <h2 className="font-bold text-sm mb-2">Today</h2>
        {today.length === 0 ? <Empty>Nobody has signed in today.</Empty> : (
          <ul className="divide-y divide-slate-100 text-sm">
            {today.map((v) => (
              <li key={v.id} className="py-1.5">{fmtDateTime(v.checked_in_at)} · <b>{v.name}</b>{v.visiting && ` → ${v.visiting}`} · {v.checked_out_at ? `out ${fmtDateTime(v.checked_out_at)}` : <Pill tone="amber">on site</Pill>}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
