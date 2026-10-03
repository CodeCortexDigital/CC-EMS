// Two panels inside an application's details: the document checklist and the application fee.
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { btn, btnGhost, errorText, input, Pill } from '@/components/common/kit';
import extras, { ChecklistItem, DocState } from '@/services/admissionsExtras.service';

const STATE: Record<DocState, { label: string; tone: 'red' | 'amber' | 'green' | 'blue' }> = {
  missing: { label: 'Missing', tone: 'red' }, uploaded: { label: 'Waiting for you to check', tone: 'amber' },
  received: { label: 'Received', tone: 'green' }, redo: { label: 'Sent back', tone: 'blue' },
};

export function ChecklistPanel({ applicationId, onChanged }: { applicationId: string; onChanged?: () => void }) {
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [redo, setRedo] = useState<{ docId: string; note: string } | null>(null);

  const load = useCallback(() => { extras.checklist(applicationId).then((r) => setItems(r.items)).catch(() => setItems([])); }, [applicationId]);
  useEffect(load, [load]);

  const review = async (docId: string, status: 'received' | 'redo', note = '') => {
    try { await extras.reviewDocument(applicationId, docId, status, note); toast.success(status === 'received' ? 'Marked received.' : 'The family was asked to send it again.'); setRedo(null); load(); onChanged?.(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };

  if (items === null) return null;
  if (items.length === 0) return <p className="text-sm text-slate-500">The school has not listed required documents (see Online form settings).</p>;
  return (
    <ul className="divide-y divide-slate-100" aria-label="Document checklist">
      {items.map((i) => (
        <li key={i.name} className="py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-sm mr-auto">{i.name}</span>
            <Pill tone={STATE[i.state].tone}>{STATE[i.state].label}</Pill>
            {i.document && <a href={i.document.url} target="_blank" rel="noreferrer" className="text-xs text-brand underline">open</a>}
            {i.document && i.state === 'uploaded' && (
              <>
                <button className={btn} onClick={() => review(i.document!.id, 'received')}>Received</button>
                <button className={btnGhost} onClick={() => setRedo({ docId: i.document!.id, note: '' })}>Send again…</button>
              </>
            )}
          </div>
          {i.state === 'redo' && i.note && <p className="text-xs text-slate-500 mt-1">Asked to send again: {i.note}</p>}
          {redo && i.document?.id === redo.docId && (
            <div className="mt-2 flex gap-2">
              <input aria-label="What to send again" className={input} placeholder="What is wrong with it?" value={redo.note} onChange={(e) => setRedo({ ...redo, note: e.target.value })} />
              <button className={btn} disabled={!redo.note.trim()} onClick={() => review(redo.docId, 'redo', redo.note)}>Ask the family</button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export function FeePanel({ applicationId, fee, onChanged }: { applicationId: string; fee: { amount: string; currency: string; status: string; note?: string } | null | undefined; onChanged: () => void }) {
  const [mode, setMode] = useState<null | 'paid' | 'waive'>(null);
  const [text, setText] = useState('');
  if (!fee) return null;

  const submit = async () => {
    try {
      if (mode === 'paid') await extras.markFeePaid(applicationId, text || 'Paid at the office');
      else await extras.waiveFee(applicationId, text);
      toast.success(mode === 'paid' ? 'Payment recorded.' : 'Fee waived.');
      setMode(null); setText(''); onChanged();
    } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };

  return (
    <div className="rounded-lg border border-slate-200 p-3" aria-label="Application fee">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-sm mr-auto">Application fee: {fee.amount} {fee.currency}</span>
        <Pill tone={fee.status === 'unpaid' ? 'red' : 'green'}>{fee.status === 'unpaid' ? 'Unpaid: application is on hold' : fee.status === 'waived' ? 'Waived' : 'Paid'}</Pill>
        {fee.status === 'unpaid' && <><button className={btn} onClick={() => setMode('paid')}>Record payment</button><button className={btnGhost} onClick={() => setMode('waive')}>Waive</button></>}
      </div>
      {fee.note && fee.status !== 'unpaid' && <p className="text-xs text-slate-500 mt-1">{fee.note}</p>}
      {mode && (
        <div className="mt-2 flex gap-2">
          <input aria-label={mode === 'paid' ? 'Payment reference' : 'Reason for waiving'} className={input} value={text} onChange={(e) => setText(e.target.value)}
            placeholder={mode === 'paid' ? 'Check number or note (optional)' : 'Why is the fee waived?'} />
          <button className={btn} disabled={mode === 'waive' && !text.trim()} onClick={submit}>{mode === 'paid' ? 'Save payment' : 'Waive fee'}</button>
          <button className={btnGhost} onClick={() => setMode(null)}>Cancel</button>
        </div>
      )}
    </div>
  );
}
