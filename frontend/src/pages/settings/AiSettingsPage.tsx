import { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { btn, card, Empty, errorText, fmtDateTime, PageHead, Pill, Spinner } from '@/components/common/kit';
import aiSettings, { AiSettings } from '@/services/aiSettings.service';

export default function AiSettingsPage() {
  const [data, setData] = useState<AiSettings | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { aiSettings.get().then(setData).catch(() => toast.error('Could not load the AI settings.')); }, []);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<AiSettings>, ok: string) => {
    setBusy(true);
    try { setData(await fn()); toast.success(ok); } catch (e) { toast.error(errorText(e, 'That did not work.')); } finally { setBusy(false); }
  };

  if (!data) return <div className="p-6"><Spinner /></div>;
  const { provider, notice, usage } = data;
  const used = usage.input_tokens + usage.output_tokens;

  return (
    <div className="p-4 sm:p-6 space-y-4 max-w-4xl">
      <PageHead title="AI assistant" hint="Choose which AI features your school uses, see what they cost this month, and read how AI is used. Everything the AI writes is a draft for a person to check." />

      <section className={card} aria-label="Provider">
        <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><Sparkles className="w-4 h-4 text-emerald-700" />AI provider</h2>
        {provider.configured
          ? <p className="text-sm text-slate-700">Connected to <b>{provider.name}</b>. {data.contact_details_shared ? 'Contact details are shared with the provider.' : 'Phone numbers, email and home addresses are masked before text is sent.'}</p>
          : <p className="text-sm text-amber-800">{provider.note}</p>}
      </section>

      <section className={`${card} ${notice.accepted ? '' : 'border-amber-300'}`} aria-label="AI use notice">
        <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-700" />How AI is used at your school</h2>
        <p className="text-sm text-slate-700 leading-relaxed">{notice.text}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {notice.accepted
            ? <Pill tone="green">Accepted by {notice.accepted_by} on {fmtDateTime(notice.accepted_at)}</Pill>
            : <><Pill tone="amber">Not accepted yet</Pill><button className={btn} disabled={busy} onClick={() => run(aiSettings.acceptNotice, 'Notice accepted.')}>I have read this and accept</button></>}
        </div>
        {!notice.accepted && <p className="text-xs text-slate-500 mt-2">New AI features that use student information stay switched off until this is accepted.</p>}
      </section>

      <section className={card} aria-label="Features">
        <h2 className="font-bold text-sm mb-2">Features</h2>
        <ul className="divide-y divide-slate-100">
          {data.features.map((f) => (
            <li key={f.key} className="py-2.5 flex items-start gap-3">
              <div className="mr-auto">
                <p className="font-semibold text-sm">{f.label}</p>
                <p className="text-xs text-slate-500">{f.description}</p>
              </div>
              <label className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" role="switch" aria-label={f.label} checked={f.enabled} disabled={busy}
                  onChange={(e) => run(() => aiSettings.setFeatures({ [f.key]: e.target.checked }), `${f.label} turned ${e.target.checked ? 'on' : 'off'}.`)} />
                {f.enabled ? 'On' : 'Off'}
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className={card} aria-label="Usage">
        <h2 className="font-bold text-sm mb-2">This month</h2>
        <p className="text-sm text-slate-700 mb-2">
          <b>{usage.requests}</b> request{usage.requests === 1 ? '' : 's'} · <b>{used.toLocaleString()}</b> tokens
          {usage.monthly_token_cap > 0 && <> of your <b>{usage.monthly_token_cap.toLocaleString()}</b> monthly allowance ({Math.min(100, Math.round((used / usage.monthly_token_cap) * 100))}%)</>}
        </p>
        {usage.by_feature.length === 0 ? <Empty>No AI use yet this month.</Empty> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th className="py-1">Feature</th><th className="text-right">Requests</th><th className="text-right">Tokens</th></tr></thead>
            <tbody>{usage.by_feature.map((r) => (
              <tr key={r.feature} className="border-t border-slate-100"><td className="py-1.5">{r.label}</td><td className="text-right">{r.requests}</td><td className="text-right">{r.tokens.toLocaleString()}</td></tr>
            ))}</tbody>
          </table>
        )}
      </section>
    </div>
  );
}
