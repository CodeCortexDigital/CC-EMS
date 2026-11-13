import { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { btn, card, Empty, errorText, fmtDateTime, PageHead, Pill, Spinner } from '@/components/common/kit';
import aiSettings, { AiSettings } from '@/services/aiSettings.service';

export default function AiSettingsPage() {
  const [data, setData] = useState<AiSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [editTraining, setEditTraining] = useState(false);
  const [form, setForm] = useState({ provider: '', confirmed_by: '', confirmed_on: '', reference: '' });

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

      <section className={`${card} ${data.ai_enabled ? '' : 'border-red-300 bg-red-50'}`} aria-label="All AI">
        <div className="flex items-start gap-3">
          <div className="mr-auto">
            <h2 className="font-bold text-sm">{data.ai_enabled ? 'AI is on for your school' : 'AI is switched OFF for your school'}</h2>
            <p className="text-xs text-slate-600">
              {data.ai_enabled
                ? 'One switch turns off every AI feature, including student risk scoring. Each feature keeps its own setting below. The change is recorded with your name and time.'
                : 'No AI feature runs, and student risk scores and flags are hidden, until you turn this back on. Your settings below are kept.'}
            </p>
          </div>
          <label className="inline-flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" role="switch" aria-label="All AI" checked={data.ai_enabled} disabled={busy}
              onChange={(e) => run(() => aiSettings.setAiEnabled(e.target.checked), e.target.checked ? 'AI turned on.' : 'AI turned off for your school.')} />
            {data.ai_enabled ? 'On' : 'Off'}
          </label>
        </div>
      </section>

      <section className={card} aria-label="Approvals">
        <h2 className="font-bold text-sm mb-1">Who approves what the AI asks for</h2>
        <p className="text-xs text-slate-600 mb-2">
          The assistant can only ask. Whoever asked can never approve their own request. Choose how many different people must approve before anything is sent,
          and, if you want, name who they are. If you name nobody, any administrator can approve. Each change is recorded with your name and time.
        </p>
        <label className="text-sm flex items-center gap-2">
          Approvals needed
          <select className="rounded border border-slate-300 px-2 py-1 text-sm" aria-label="Approvals needed" value={data.approval.required} disabled={busy}
            onChange={(e) => run(() => aiSettings.setApproval(Number(e.target.value) as 1 | 2, data.approval.approvers), 'Approval rule saved.')}>
            <option value={1}>One person</option>
            <option value={2}>Two different people</option>
          </select>
        </label>
        <fieldset className="mt-2">
          <legend className="text-xs font-semibold text-slate-700">People who may approve {data.approval.approvers.length === 0 && <span className="font-normal text-slate-500">(none named: any administrator)</span>}</legend>
          <ul className="mt-1 space-y-1">
            {data.approval.candidates.map((c) => (
              <li key={c.id}>
                <label className="inline-flex items-center gap-2 text-sm">
                  <input type="checkbox" aria-label={`Approver ${c.name}`} disabled={busy} checked={data.approval.approvers.includes(c.id)}
                    onChange={(e) => run(() => aiSettings.setApproval(data.approval.required,
                      e.target.checked ? [...data.approval.approvers, c.id] : data.approval.approvers.filter((x) => x !== c.id)), 'Approvers saved.')} />
                  {c.name} <span className="text-xs text-slate-500">({c.role}, {c.email})</span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      </section>

      <section className={card} aria-label="Provider">
        <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><Sparkles className="w-4 h-4 text-emerald-700" />AI provider</h2>
        {provider.configured
          ? <p className="text-sm text-slate-700">Connected to <b>{provider.name}</b>. {data.contact_details_shared ? 'Contact details are shared with the provider.' : 'Phone numbers, email and home addresses are masked before text is sent.'}</p>
          : <p className="text-sm text-amber-800">{provider.note}</p>}
      </section>

      <section className={`${card} ${data.training.confirmed && !data.training.provider_mismatch ? '' : 'border-amber-300'}`} aria-label="AI provider training">
        <h2 className="font-bold text-sm mb-1 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-700" />Provider does not train on your data</h2>
        <p className="text-sm text-slate-700 leading-relaxed">Education guidelines ask schools to use AI services that do not learn from what is typed in. Record the provider's written confirmation here, so you can show it to the education board.</p>
        <ul className="mt-2 list-disc pl-5 text-xs text-slate-600">
          {data.always_masked.map((m) => <li key={m}>{m} are always hidden before text is sent.</li>)}
        </ul>
        {data.training.confirmed && !editTraining ? (
          <div className="mt-3 space-y-1 text-sm">
            <Pill tone="green">Confirmed by {data.training.provider} on {data.training.confirmed_on}</Pill>
            <p className="text-slate-600">{data.training.confirmed_by ? `Given by ${data.training.confirmed_by}. ` : ''}{data.training.reference}</p>
            <p className="text-xs text-slate-500">Recorded by {data.training.recorded_by} on {fmtDateTime(data.training.recorded_at)}</p>
            {data.training.provider_mismatch && <p className="text-amber-800">This server uses a different AI provider than the one confirmed. Get a confirmation for the provider in use.</p>}
            <div className="flex gap-3 pt-1">
              <button className="text-xs font-semibold text-blue-600" onClick={() => { setForm({ provider: data.training.provider, confirmed_by: data.training.confirmed_by, confirmed_on: data.training.confirmed_on, reference: data.training.reference }); setEditTraining(true); }}>Update</button>
              <button className="text-xs font-semibold text-rose-700" disabled={busy} onClick={() => run(aiSettings.clearTraining, 'Removed.')}>Remove</button>
            </div>
          </div>
        ) : (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {!data.training.confirmed && <p className="sm:col-span-2"><Pill tone="amber">Not confirmed yet</Pill></p>}
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="AI provider" placeholder="AI provider, e.g. Anthropic" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} />
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" type="date" aria-label="Date of confirmation" value={form.confirmed_on} onChange={(e) => setForm({ ...form, confirmed_on: e.target.value })} />
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Given by" placeholder="Given by (name or team)" value={form.confirmed_by} onChange={(e) => setForm({ ...form, confirmed_by: e.target.value })} />
            <input className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Where the confirmation is kept" placeholder="Where it is kept (email, contract clause, link)" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
            <div className="sm:col-span-2 flex gap-2">
              <button className={btn} disabled={busy} onClick={async () => { await run(() => aiSettings.saveTraining(form), 'Recorded.'); setEditTraining(false); }}>Record the confirmation</button>
              {editTraining && <button className="rounded-lg border border-slate-300 px-3 py-2 text-sm" onClick={() => setEditTraining(false)}>Cancel</button>}
            </div>
          </div>
        )}
      </section>

      <section className={card} aria-label="AI controls">
        <h2 className="font-bold text-sm mb-1">Rules for using AI at your school</h2>
        <p className="text-xs text-slate-600 mb-2">These are off until you switch them on, so nothing stops without warning. Each change is recorded with your name and time. They apply while an AI provider is connected.</p>
        <ul className="divide-y divide-slate-100">
          {([
            ['require_user_notice', 'Everyone accepts the AI use notice first', `Each person reads a short notice and accepts it before their first use. ${data.controls.accepted_by} ${data.controls.accepted_by === 1 ? 'person has' : 'people have'} accepted it so far.`],
            ['require_training', 'Pause AI until the provider’s no-training confirmation is recorded', 'No AI request is sent while the record above is missing, or is for a different provider than the one in use.'],
            ['mask_names', 'Replace student names before anything is sent', 'Student names in questions and in the school information the AI reads are replaced by codes and put back in the answer. Only names as written in the student record are replaced, and an answer that shows a real name is marked in its record.'],
          ] as const).map(([key, label, text]) => (
            <li key={key} className="py-2.5 flex items-start gap-3">
              <div className="mr-auto"><p className="font-semibold text-sm">{label}</p><p className="text-xs text-slate-500">{text}</p></div>
              <input type="checkbox" role="switch" aria-label={label} checked={data.controls[key]} disabled={busy}
                onChange={(e) => run(() => aiSettings.setControl({ [key]: e.target.checked }), e.target.checked ? 'Switched on.' : 'Switched off.')} />
            </li>
          ))}
        </ul>
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
