// Taking a book back from a loan's own Return button: the book in hand must be the one on the loan.
// The desk scans (or types) its barcode; a wrong book returns nothing and the message says which book was scanned.
// If the label is torn or will not scan, the desk can confirm by hand and the loan records that it was done that way.
import { useEffect, useRef, useState } from 'react';
import { Loader2, ScanLine } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import library, { errorText, type Loan } from '@/services/library.service';

type Result = Awaited<ReturnType<typeof library.returnBook>>;

export default function ReturnCheck({ loan, onClose, onDone }: { loan: Loan; onClose: () => void; onDone: (r: Result) => void }) {
  const [code, setCode] = useState('');
  const [manual, setManual] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, [manual]);

  const submit = async () => {
    if (busy || (!manual && !code.trim())) return;
    setBusy(true);
    setError('');
    try { onDone(await library.returnBook(code.trim(), { loan_id: loan.id, manual })); }
    catch (e) { setError(errorText(e, 'Could not return this book.')); setCode(''); ref.current?.focus(); }
    finally { setBusy(false); }
  };

  return (
    <Modal open onClose={onClose} title="Check the book" size="sm"
      footer={<>
        <button type="button" onClick={onClose} className="px-3 py-2 rounded-lg border border-slate-300 text-sm font-medium">Cancel</button>
        <button type="button" onClick={submit} disabled={busy || (!manual && !code.trim())}
          className="px-3.5 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium disabled:opacity-50 inline-flex items-center gap-1.5">
          {busy && <Loader2 size={14} className="animate-spin" />}{manual ? 'Return without scanning' : 'Return'}
        </button>
      </>}>
      <div className="space-y-3 text-sm">
        <p>Returning <b>{loan.title}</b> from <b>{loan.member.name}</b>. Scan the barcode on the book you are holding <span className="text-slate-500">(it should be {loan.barcode})</span>.</p>
        {!manual && (
          <div className="relative">
            <ScanLine size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input ref={ref} aria-label="Barcode of the book in your hand" placeholder="Scan or type the barcode"
              className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm" value={code}
              onChange={(e) => { setCode(e.target.value); setError(''); }} onKeyDown={(e) => { if (e.key === 'Enter') submit(); }} />
          </div>
        )}
        {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-rose-800">{error}</p>}
        <label className="flex items-start gap-2 text-slate-600">
          <input type="checkbox" className="mt-0.5" checked={manual} onChange={(e) => { setManual(e.target.checked); setError(''); }} />
          <span>The label is torn or will not scan. I have checked the title myself. <span className="text-slate-400">(This is recorded on the loan.)</span></span>
        </label>
      </div>
    </Modal>
  );
}
