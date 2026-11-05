// The decision record for one AI request: what was asked, what it was based on, every recorded step and who took it, and whether the
// trail still verifies. It is the page an outside reviewer can read without help from whoever built the system.
import { useEffect, useState } from 'react';
import { CheckCircle2, Download, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { Pill, Spinner, btnGhost, errorText, fmtDateTime } from '@/components/common/kit';
import ai, { type DecisionRecord } from '@/services/aiGovernance.service';

const CONTROL_LABEL: Record<string, string> = {
  ai_chat_enabled: 'Assistant chat switched on', contact_details_shared: 'Contact details sent to the provider', use_notice_version: 'AI use notice version',
  use_notice_accepted: 'AI use notice accepted by the school', rate_limit_per_window: 'Requests allowed per person per window',
  rate_window_seconds: 'Window (seconds)', monthly_token_cap: 'Monthly token cap for the school (0 = none)',
};
const show = (v: unknown) => (typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v));

export default function DecisionRecordModal({ id, onClose }: { id: string; onClose: () => void }) {
  const [rec, setRec] = useState<DecisionRecord | null>(null);
  useEffect(() => {
    let live = true;
    ai.record(id).then((r) => live && setRec(r)).catch((e) => { toast.error(errorText(e, 'Could not load the decision record.')); onClose(); });
    return () => { live = false; };
  }, [id, onClose]);

  const download = async () => {
    try {
      const url = URL.createObjectURL(await ai.downloadRecord(id));
      const a = document.createElement('a');
      a.href = url; a.download = `decision-record-${id}.json`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(errorText(e, 'Could not download the record.')); }
  };

  const b = rec?.basis;
  return (
    <Modal open onClose={onClose} title="Decision record" size="xl"
      description="What was asked, what it was based on, who decided, and whether the trail still verifies.">
      {!rec ? <Spinner /> : (
        <div className="space-y-4 text-sm" data-testid="decision-record">
          <div className={`flex items-start gap-2 rounded-lg border p-3 ${rec.chain.verifies && rec.basis_matches_trail ? 'border-emerald-200 bg-emerald-50' : 'border-red-300 bg-red-50'}`}>
            {rec.chain.verifies && rec.basis_matches_trail
              ? <CheckCircle2 className="w-4 h-4 text-emerald-700 mt-0.5" /> : <ShieldAlert className="w-4 h-4 text-red-700 mt-0.5" />}
            <div>
              <p className="font-bold">{rec.chain.verifies && rec.basis_matches_trail ? 'The trail verifies' : 'The trail does NOT verify'}</p>
              <p className="text-xs text-slate-600">
                {rec.chain.records_checked} decision record(s) for this school were checked{rec.basis_matches_trail ? '' : ', and what this request was based on does not match what was recorded when it was made'}.
                {rec.chain.problems.map((p) => <span key={p} className="block text-red-700">{p}</span>)}
              </p>
              <p className="text-[11px] text-slate-500 mt-1">{rec.note}</p>
            </div>
          </div>

          <section>
            <h4 className="font-bold mb-1">The request</h4>
            <p>{rec.request.summary} <Pill tone={rec.request.status === 'executed' ? 'green' : rec.request.status === 'pending' ? 'amber' : 'slate'}>{rec.request.status}</Pill></p>
            <p className="text-xs text-slate-500">Asked by {rec.request.requested_by} ({rec.request.requester_role}) on {fmtDateTime(rec.request.created_at)}.</p>
            <p className="text-xs text-slate-500">Arguments: <code>{JSON.stringify(rec.request.arguments)}</code></p>
          </section>

          <section>
            <h4 className="font-bold mb-1">What it was based on</h4>
            <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-1 text-xs">
              <dt className="text-slate-500">Provider and model</dt><dd>{b?.provider || 'not recorded'} / {b?.model || 'not recorded'}</dd>
              <dt className="text-slate-500">Instructions fingerprint</dt><dd className="font-mono break-all">{b?.instructions_sha256 || 'not recorded'}</dd>
              <dt className="text-slate-500">What the person asked</dt><dd>{b?.asked || 'not recorded'}</dd>
              <dt className="text-slate-500">Sources used</dt><dd>{b?.sources?.length ? b.sources.map((s) => s.title).join(', ') : 'none'}</dd>
              <dt className="text-slate-500">Recorded at</dt><dd>{b?.recorded_at ? fmtDateTime(b.recorded_at) : 'not recorded'}</dd>
            </dl>
            {!!b?.tool_outputs_sent?.length && (
              <details className="mt-2"><summary className="cursor-pointer text-xs font-bold">Data sent to the model, after masking ({b.tool_outputs_sent.length})</summary>
                {b.tool_outputs_sent.map((t, i) => <pre key={i} className="mt-1 max-h-40 overflow-auto rounded bg-slate-50 p-2 text-[11px] whitespace-pre-wrap">{t.tool}: {t.sent_to_model}</pre>)}
              </details>
            )}
            <details className="mt-2"><summary className="cursor-pointer text-xs font-bold">Controls that were on at the time</summary>
              <ul className="mt-1 text-xs space-y-0.5">
                {Object.entries(b?.controls || {}).map(([k, v]) => <li key={k}><span className="text-slate-500">{CONTROL_LABEL[k] || k}:</span> {show(v)}</li>)}
              </ul>
            </details>
          </section>

          <section>
            <h4 className="font-bold mb-1">Every recorded step</h4>
            <ol className="space-y-1">
              {rec.trail.map((t) => (
                <li key={t.seq} className="rounded border border-slate-200 p-2 text-xs">
                  <span className="font-bold">#{t.seq} {t.status}</span> by {t.by || 'unknown'} on {fmtDateTime(t.at)}
                  {!!(t.data as { note?: string }).note && <> · note: {(t.data as { note?: string }).note}</>}
                  <span className="block font-mono text-[10px] text-slate-400 break-all">hash {t.hash}</span>
                </li>
              ))}
            </ol>
            <p className="text-[11px] text-slate-500 mt-1">Newest hash for the school: <span className="font-mono break-all">{rec.chain.newest_hash}</span></p>
          </section>

          <div className="flex justify-end"><button className={btnGhost} onClick={download}><Download className="w-3.5 h-3.5 inline mr-1" />Download as a file</button></div>
        </div>
      )}
    </Modal>
  );
}
