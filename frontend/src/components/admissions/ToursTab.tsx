import { useCallback, useEffect, useState } from 'react';
import { CalendarPlus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDateTime, input, nowLocal, Pill, Spinner } from '@/components/common/kit';
import extras, { TourBooking, TourSlot } from '@/services/admissionsExtras.service';

export default function ToursTab() {
  const [slots, setSlots] = useState<TourSlot[] | null>(null);
  const [bookings, setBookings] = useState<TourBooking[]>([]);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    extras.slots().then(setSlots).catch(() => setSlots([]));
    extras.bookings().then(setBookings).catch(() => setBookings([]));
  }, []);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(errorText(e, 'That did not work.')); } };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <p className="text-sm text-slate-500 mr-auto max-w-2xl">Offer times for school tours and interviews. Families book one from their application link, and are reminded the day before.</p>
        <button className={btn} onClick={() => setAdding(true)}><CalendarPlus className="inline w-3.5 h-3.5 mr-1" />Add a time</button>
      </div>

      {slots === null ? <Spinner /> : slots.length === 0 ? <Empty>No tour or interview times yet.</Empty> : (
        <ul className="space-y-2">
          {slots.map((s) => {
            const mine = bookings.filter((b) => b.slot === s.id);
            return (
              <li key={s.id} className={card}>
                <div className="flex flex-wrap items-center gap-3">
                  <Pill tone={s.kind === 'tour' ? 'blue' : 'amber'}>{s.kind === 'tour' ? 'Tour' : 'Interview'}</Pill>
                  <b className="text-sm">{fmtDateTime(s.starts_at)}</b>
                  <span className="text-xs text-slate-500">{s.location}{s.host && ` · ${s.host}`} · {s.booked}/{s.capacity} booked</span>
                  {!s.is_open && <Pill tone="slate">closed</Pill>}
                  <span className="ml-auto flex gap-2">
                    <button className={btnGhost} onClick={() => run(() => extras.saveSlot(s.id, { is_open: !s.is_open }), s.is_open ? 'Closed to new bookings.' : 'Reopened.')}>{s.is_open ? 'Close' : 'Reopen'}</button>
                    <button aria-label="Delete this time" className="text-slate-400 hover:text-rose-600" onClick={() => window.confirm('Delete this time?') && run(() => extras.deleteSlot(s.id), 'Deleted.')}><Trash2 className="w-4 h-4" /></button>
                  </span>
                </div>
                {mine.length > 0 && (
                  <ul className="mt-2 text-sm border-t border-slate-100 pt-2">
                    {mine.map((b) => (
                      <li key={b.id} className="flex items-center gap-2 py-0.5">{b.student_name} <span className="text-slate-400">{b.application_no}</span>
                        <button className="ml-auto text-xs underline text-slate-500" onClick={() => window.confirm(`Cancel ${b.student_name}'s booking?`) && run(() => extras.cancelBooking(b.id), 'Booking cancelled.')}>Cancel booking</button></li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {adding && <SlotDialog onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load(); }} />}
    </div>
  );
}

function SlotDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ kind: 'tour', starts_at: nowLocal(), ends_at: nowLocal(), location: '', host: '', capacity: '1' });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await extras.saveSlot(null, { kind: f.kind as 'tour' | 'interview', starts_at: new Date(f.starts_at).toISOString(), ends_at: new Date(f.ends_at).toISOString(), location: f.location, host: f.host, capacity: Number(f.capacity) });
      toast.success('Time added.');
      onSaved();
    } catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title="Add a tour or interview time">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Kind"><select aria-label="Kind" className={input} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="tour">School tour</option><option value="interview">Interview</option></select></Field>
          <Field label="Families per time"><input aria-label="Capacity" type="number" min={1} className={input} value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></Field>
          <Field label="Starts"><input aria-label="Starts" type="datetime-local" className={input} value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
          <Field label="Ends"><input aria-label="Ends" type="datetime-local" className={input} value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} /></Field>
          <Field label="Where"><input aria-label="Where" className={input} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="Front office" /></Field>
          <Field label="Led by"><input aria-label="Led by" className={input} value={f.host} onChange={(e) => setF({ ...f, host: e.target.value })} /></Field>
        </div>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving} onClick={save}>Add</button></div>
      </div>
    </Modal>
  );
}
