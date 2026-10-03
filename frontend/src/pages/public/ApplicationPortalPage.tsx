// What a family does after applying, with only their application number and tracking code (no account):
// answer a seat offer, pay the application fee, send documents, and book a school tour or interview.
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CalendarCheck, CreditCard, FileUp, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { btn, btnGhost, card, errorText, fmtDateTime, input, Pill, Spinner } from '@/components/common/kit';
import { family, ChecklistItem, Credentials, DocState, FamilyFee, FamilyOffer, FamilyTours } from '@/services/admissionsExtras.service';

const STATE: Record<DocState, { label: string; tone: 'red' | 'amber' | 'green' | 'blue' }> = {
  missing: { label: 'Needed', tone: 'red' }, uploaded: { label: 'Sent: the school will check it', tone: 'amber' },
  received: { label: 'Received', tone: 'green' }, redo: { label: 'Please send again', tone: 'blue' },
};

export default function ApplicationPortalPage() {
  const [params] = useSearchParams();
  const [creds, setCreds] = useState<Credentials | null>(() => {
    const no = params.get('no'), token = params.get('token');
    return no && token ? { no, token } : null;
  });
  const [draft, setDraft] = useState({ no: params.get('no') || '', token: params.get('token') || '' });

  return (
    <div className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="max-w-3xl mx-auto space-y-4">
        <header>
          <h1 className="text-2xl font-black text-slate-900">Your application</h1>
          <p className="text-sm text-slate-500">Answer an offer, pay the application fee, send documents and book a visit. Use the application number and tracking code from your confirmation email.</p>
        </header>
        {!creds ? (
          <form className={`${card} space-y-3`} onSubmit={(e) => { e.preventDefault(); setCreds({ no: draft.no.trim(), token: draft.token.trim() }); }}>
            <label className="block text-xs font-bold text-slate-600">Application number<input aria-label="Application number" className={`${input} mt-1`} value={draft.no} onChange={(e) => setDraft({ ...draft, no: e.target.value })} placeholder="APP-2026-0001" /></label>
            <label className="block text-xs font-bold text-slate-600">Tracking code<input aria-label="Tracking code" className={`${input} mt-1`} value={draft.token} onChange={(e) => setDraft({ ...draft, token: e.target.value })} /></label>
            <button className={btn} disabled={!draft.no.trim() || !draft.token.trim()}>Open my application</button>
          </form>
        ) : <Sections creds={creds} />}
      </div>
    </div>
  );
}

function Sections({ creds }: { creds: Credentials }) {
  const [offer, setOffer] = useState<FamilyOffer | null | undefined>(undefined);
  const [bad, setBad] = useState(false);

  const loadOffer = useCallback(() => {
    family.offer(creds).then((o) => { setOffer(o); setBad(false); }).catch(() => { setOffer(null); setBad(true); });
  }, [creds]);
  useEffect(loadOffer, [loadOffer]);

  if (offer === undefined) return <Spinner />;
  if (bad || !offer) return <div className={card} role="alert"><p className="text-sm text-rose-800">We could not find an application with that number and tracking code. Please check them and try again.</p></div>;

  return (
    <>
      <div className={`${card} flex flex-wrap items-center gap-3`}>
        <div className="mr-auto"><p className="font-bold">{offer.student}</p><p className="text-xs text-slate-500">{offer.application_no} · {offer.grade}</p></div>
        <Pill tone="blue">{offer.status}</Pill>
      </div>
      {offer.offer && <OfferCard creds={creds} offer={offer} onDone={loadOffer} />}
      <FeeCard creds={creds} />
      <DocumentsCard creds={creds} />
      <ToursCard creds={creds} />
    </>
  );
}

function OfferCard({ creds, offer, onDone }: { creds: Credentials; offer: FamilyOffer; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const answer = async (decision: 'accept' | 'decline') => {
    if (decision === 'decline' && !window.confirm('Decline this place? It will be offered to another family.')) return;
    setBusy(true);
    try { await family.respond(creds, decision); toast.success(decision === 'accept' ? 'Wonderful! The school will be in touch about enrolment.' : 'Thank you for letting us know.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not send your answer.')); } finally { setBusy(false); }
  };
  return (
    <section className="rounded-xl border-2 border-emerald-400 bg-emerald-50 p-4" aria-label="A place is available">
      <h2 className="font-black text-emerald-900 flex items-center gap-2"><Sparkles className="w-4 h-4" />A place is available for {offer.student}</h2>
      <p className="text-sm text-emerald-900 mt-1">Please answer before <b>{fmtDateTime(offer.offer!.expires_at)}</b>. After that the place is offered to the next family.</p>
      <div className="flex gap-2 mt-3"><button className={btn} disabled={busy} onClick={() => answer('accept')}>Accept the place</button><button className={btnGhost} disabled={busy} onClick={() => answer('decline')}>Decline</button></div>
    </section>
  );
}

function FeeCard({ creds }: { creds: Credentials }) {
  const [data, setData] = useState<FamilyFee | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { family.fee(creds).then(setData).catch(() => setData(null)); }, [creds]);
  if (!data?.fee) return null;
  const pay = async () => {
    setBusy(true);
    const back = `${window.location.origin}/apply/manage?no=${encodeURIComponent(creds.no)}&token=${encodeURIComponent(creds.token)}`;
    try { window.location.href = (await family.checkout(creds, back, back)).url; } catch (e) { toast.error(errorText(e, 'Online payment is not available. Please contact the school office.')); setBusy(false); }
  };
  return (
    <section className={card} aria-label="Application fee">
      <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><CreditCard className="w-4 h-4" />Application fee</h2>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm mr-auto">{data.fee.amount} {data.fee.currency}</span>
        {data.fee.status === 'unpaid' ? <><Pill tone="red">Not paid yet</Pill><button className={btn} disabled={busy} onClick={pay}>Pay by card</button></> : <Pill tone="green">{data.fee.status === 'waived' ? 'No fee to pay' : 'Paid. Thank you'}</Pill>}
      </div>
      {data.fee.status === 'unpaid' && <p className="text-xs text-slate-500 mt-2">The school starts reviewing the application once the fee is paid.</p>}
    </section>
  );
}

function DocumentsCard({ creds }: { creds: Credentials }) {
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [busy, setBusy] = useState('');
  useEffect(() => { family.documents(creds).then((r) => setItems(r.items)).catch(() => setItems([])); }, [creds]);
  if (!items || items.length === 0) return null;

  const send = async (name: string, file: File) => {
    setBusy(name);
    try { setItems((await family.upload(creds, name, file)).items); toast.success(`${name} sent.`); } catch (e) { toast.error(errorText(e, 'Could not send the file.')); } finally { setBusy(''); }
  };
  return (
    <section className={card} aria-label="Documents">
      <h2 className="font-bold text-sm mb-2 flex items-center gap-2"><FileUp className="w-4 h-4" />Documents</h2>
      <ul className="divide-y divide-slate-100">
        {items.map((i) => (
          <li key={i.name} className="py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold mr-auto">{i.name}</span>
              <Pill tone={STATE[i.state].tone}>{STATE[i.state].label}</Pill>
              {i.state !== 'received' && (
                <label className={`${btnGhost} cursor-pointer`}>{busy === i.name ? 'Sending…' : i.state === 'missing' ? 'Choose file' : 'Send a new file'}
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" className="sr-only" aria-label={`Upload ${i.name}`} disabled={busy === i.name}
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) send(i.name, f); e.target.value = ''; }} />
                </label>
              )}
            </div>
            {i.state === 'redo' && i.note && <p className="text-xs text-blue-800 mt-1">The school asked: {i.note}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ToursCard({ creds }: { creds: Credentials }) {
  const [kind, setKind] = useState<'tour' | 'interview'>('tour');
  const [data, setData] = useState<FamilyTours | null>(null);
  const load = useCallback(() => { family.tours(creds, kind).then(setData).catch(() => setData({ slots: [], my_bookings: [] })); }, [creds, kind]);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(errorText(e, 'That did not work.')); } };
  const mine = (data?.my_bookings || []).filter((b) => b.kind === kind);

  return (
    <section className={card} aria-label="Tours and interviews">
      <h2 className="font-bold text-sm mb-2 flex items-center gap-2"><CalendarCheck className="w-4 h-4" />Visit the school</h2>
      <div className="flex gap-2 mb-3">
        {([['tour', 'School tour'], ['interview', 'Interview']] as const).map(([k, l]) => (
          <button key={k} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${kind === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`} onClick={() => setKind(k)}>{l}</button>
        ))}
      </div>
      {mine.map((b) => (
        <div key={b.id} className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 mb-2 flex items-center gap-3 text-sm">
          <span className="mr-auto">You are booked for <b>{fmtDateTime(b.starts_at)}</b>.</span>
          <button className={btnGhost} onClick={() => run(() => family.cancelBooking(creds, b.id), 'Booking cancelled.')}>Cancel</button>
        </div>
      ))}
      {data === null ? <Spinner /> : mine.length > 0 ? null : data.slots.length === 0 ? <p className="text-sm text-slate-500">No times are available right now. Please check again soon.</p> : (
        <ul className="divide-y divide-slate-100">
          {data.slots.map((s) => (
            <li key={s.id} className="py-2 flex flex-wrap items-center gap-3 text-sm">
              <b>{fmtDateTime(s.starts_at)}</b><span className="text-xs text-slate-500 mr-auto">{s.location}{s.host && ` · ${s.host}`}</span>
              <button className={btn} onClick={() => run(() => family.book(creds, s.id), 'Booked. A confirmation email is on its way.')}>Book this time</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
