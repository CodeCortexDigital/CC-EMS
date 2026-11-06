// The school's whole decision trail in one place: assistant answers, risk-flag reviews, approval steps and AI setting changes.
// Administrators only. Each entry opens with its data, its hashes and whether the trail still verifies, and can be saved as a file.
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Download, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { Empty, Pill, Spinner, btn, btnGhost, card, errorText, fmtDateTime } from '@/components/common/kit';
import ai, { type TrailEntry, type TrailEntryDetail, type TrailKind } from '@/services/aiGovernance.service';

const KINDS: [TrailKind | 'all', string][] = [['all', 'All'], ['answer', 'Assistant answers'], ['risk', 'Risk flag reviews'], ['approval', 'Approval steps'], ['settings', 'Setting changes']];

function EntryModal({ seq, onClose }: { seq: number; onClose: () => void }) {
  const [e, setE] = useState<TrailEntryDetail | null>(null);
  useEffect(() => {
    let live = true;
    ai.trailEntry(seq).then((r) => live && setE(r)).catch((err) => { toast.error(errorText(err, 'Could not load the record.')); onClose(); });
    return () => { live = false; };
  }, [seq, onClose]);

  const download = async () => {
    try {
      const url = URL.createObjectURL(await ai.downloadTrailEntry(seq));
      const a = document.createElement('a');
      a.href = url; a.download = `decision-record-${seq}.json`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { toast.error(errorText(err, 'Could not download the record.')); }
  };

  return (
    <Modal open onClose={onClose} title={e ? `${e.kind_label} no. ${e.seq}` : 'Decision record'} size="xl"
      description="What was recorded, who by, and whether the trail still verifies.">
      {!e ? <Spinner /> : (
        <div className="space-y-3 text-sm" data-testid="trail-entry">
          <div className={`flex items-start gap-2 rounded-lg border p-3 ${e.chain.verifies ? 'border-emerald-200 bg-emerald-50' : 'border-red-300 bg-red-50'}`}>
            {e.chain.verifies ? <CheckCircle2 className="w-4 h-4 text-emerald-700 mt-0.5" /> : <ShieldAlert className="w-4 h-4 text-red-700 mt-0.5" />}
            <div>
              <p className="font-bold">{e.chain.verifies ? 'The trail verifies' : 'The trail does NOT verify'}</p>
              <p className="text-xs text-slate-600">{e.chain.records_checked} record(s) checked.
                {e.chain.problems.map((p) => <span key={p} className="block text-red-700">{p}</span>)}</p>
              <p className="text-[11px] text-slate-500 mt-1">{e.note}</p>
            </div>
          </div>
          <p>{e.summary}</p>
          <p className="text-xs text-slate-500">By {e.by || 'unknown'} on {fmtDateTime(e.at)}.</p>
          <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto max-h-80 whitespace-pre-wrap">{JSON.stringify(e.data, null, 2)}</pre>
          <p className="text-[11px] text-slate-500 break-all">Hash {e.hash}<br />Previous hash {e.previous_hash || '(first record)'}</p>
          <button type="button" className={btnGhost} onClick={download}><Download className="w-3.5 h-3.5" /> Download this record</button>
        </div>
      )}
    </Modal>
  );
}

export default function TrailRecords() {
  const [kind, setKind] = useState<TrailKind | 'all'>('all');
  const [rows, setRows] = useState<TrailEntry[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(async () => {
    try { setRows(await ai.trail(kind)); } catch (e) { toast.error(errorText(e, 'Could not load the records.')); setRows([]); }
  }, [kind]);
  useEffect(() => { setRows(null); load(); }, [load]);
  const close = useCallback(() => setOpen(null), []);

  return (
    <section aria-label="Decision records" className="space-y-3">
      <p className="text-sm text-slate-600 max-w-3xl">
        Everything the AI side decided or was asked to decide for this school, newest first: what the assistant answered, which risk flags a person confirmed or
        dismissed, each approval step and every change to the AI settings. Each entry is linked to the one before it, so a change or a missing entry is noticed.
      </p>
      <div className="flex flex-wrap gap-2">
        {KINDS.map(([k, label]) => (
          <button key={k} type="button" className={kind === k ? btn : btnGhost} onClick={() => setKind(k)}>{label}</button>
        ))}
      </div>
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty>No records of this kind yet.</Empty> : rows.map((r) => (
        <div key={r.seq} className={card} data-testid="trail-row">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="blue">{r.kind_label}</Pill>
            <span className="text-xs text-slate-500">no. {r.seq} · {fmtDateTime(r.at)} · {r.by || 'unknown'}</span>
            <button type="button" className={`${btnGhost} ml-auto`} onClick={() => setOpen(r.seq)}>Open</button>
          </div>
          <p className="text-sm mt-1">{r.summary}</p>
        </div>
      ))}
      {open !== null && <EntryModal seq={open} onClose={close} />}
    </section>
  );
}
