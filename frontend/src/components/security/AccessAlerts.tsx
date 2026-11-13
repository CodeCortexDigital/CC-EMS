import { useEffect, useState } from 'react';
import { AlertTriangle, FileText, Loader2, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import security, { AccessAlertList, AccessAlertRow, AlertLimits, BreachDraft } from '@/services/security.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm';
const input = 'rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white';
const when = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' } as any);
const TONE: Record<string, string> = { open: 'bg-amber-100 text-amber-800', reviewed: 'bg-emerald-100 text-emerald-700', dismissed: 'bg-slate-100 text-slate-600' };
const LIMIT_LABELS: Array<[keyof AlertLimits, string]> = [['views', 'Different student records opened in one hour'], ['night_views', 'Records opened at night (22:00 to 06:00)'],
  ['exports', 'Exports in one hour'], ['refused', 'Refused requests in one hour']];
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));
const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;

/** Security & privacy → Access review → alerts: signs that personal information may have been used in an unusual way, to review, and a draft breach report. */
export default function AccessAlerts() {
  const [data, setData] = useState<AccessAlertList | null>(null);
  const [deciding, setDeciding] = useState<{ alert: AccessAlertRow; status: 'reviewed' | 'dismissed' } | null>(null);
  const [note, setNote] = useState('');
  const [draft, setDraft] = useState<BreachDraft | null>(null);
  const [limits, setLimits] = useState<AlertLimits | null>(null);
  const load = () => security.accessAlerts().then((d) => { setData(d); setLimits(d.limits); }).catch(() => { setData({ results: [], open: 0, new: 0, limits: { views: 30, night_views: 5, exports: 5, refused: 10 }, defaults: { views: 30, night_views: 5, exports: 5, refused: 10 }, kinds: {} }); toast.error('Could not load the alerts.'); });
  useEffect(() => { load(); }, []);

  const decide = async () => {
    if (!deciding) return;
    try { await security.updateAlert(deciding.alert.id, deciding.status, note); setDeciding(null); setNote(''); toast.success('Recorded.'); load(); }
    catch (e) { toast.error(errorText(e, 'Could not record that.')); }
  };
  const reopen = async (a: AccessAlertRow) => { try { await security.updateAlert(a.id, 'open', ''); load(); } catch (e) { toast.error(errorText(e, 'Could not re-open it.')); } };
  const openDraft = async (a: AccessAlertRow, lang: 'ja' | 'en') => { try { setDraft(await security.alertReport(a.id, lang)); } catch (e) { toast.error(errorText(e, 'Could not make the draft.')); } };
  const saveLimits = async () => { if (!limits) return; try { const d = await security.saveAlertLimits(limits); setData(d); setLimits(d.limits); toast.success('The limits were saved.'); } catch (e) { toast.error(errorText(e, 'Could not save the limits.')); } };
  const print = () => {
    if (!draft) return;
    const w = window.open('', '_blank');
    if (!w) { toast.error('Allow pop-ups to print.'); return; }
    w.document.write(`<!doctype html><meta charset="utf-8"><title>${esc(draft.title)}</title><style>body{font:12px/1.5 sans-serif;margin:20px}h1{font-size:16px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;padding:5px;vertical-align:top;text-align:left}th{width:28%;background:#eee}</style><h1>${esc(draft.title)}</h1><p>${esc(draft.school)} · ${esc(draft.prepared_on)}</p><table>${draft.sections.map((s) => `<tr><th>${esc(s.heading)}</th><td>${esc(s.text)}</td></tr>`).join('')}</table>${draft.guidance.map((g) => `<p>${esc(g)}</p>`).join('')}<p><i>${esc(draft.note)}</i></p>`);
    w.document.close(); w.focus(); w.print();
  };

  return (
    <section className={`${card} p-5`} aria-labelledby="alerts-title">
      <h2 id="alerts-title" className="flex items-center gap-2 font-bold text-slate-800"><AlertTriangle size={16} /> Alerts for unusual use</h2>
      <p className="mt-1 text-sm text-slate-600">The system looks for bursts: many student records opened in an hour, records opened at night, many exports, many refused requests. An alert is a sign, not a finding: look into it, then record what you found. If personal data may have leaked, start a draft report from the alert.</p>
      {!data ? <div className="py-6 text-center"><Loader2 className="inline animate-spin text-slate-400" /></div> : data.results.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">No alerts.</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100">
          {data.results.map((a) => (
            <li key={a.id} className="py-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span><span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${TONE[a.status]}`}>{a.status_label}</span> <span className="font-semibold text-slate-800 ml-1">{a.kind_label}</span> · {a.who} <span className="text-xs text-slate-500">({a.email})</span></span>
                <span className="text-xs text-slate-500">{when(a.window_start)} · {a.count} (limit {a.limit})</span>
              </div>
              {a.note && <p className="mt-1 text-slate-600">{a.note} <span className="text-xs text-slate-400">· {a.reviewed_by}</span></p>}
              <div className="mt-1 flex flex-wrap gap-3 text-xs font-semibold">
                {a.status === 'open' ? <>
                  <button className="text-emerald-700" onClick={() => { setDeciding({ alert: a, status: 'reviewed' }); setNote(''); }}>Reviewed: record what I found</button>
                  <button className="text-slate-600" onClick={() => { setDeciding({ alert: a, status: 'dismissed' }); setNote(''); }}>Not a problem</button>
                </> : <button className="text-blue-600" onClick={() => reopen(a)}>Re-open</button>}
                <button className="inline-flex items-center gap-1 text-blue-600" onClick={() => openDraft(a, 'ja')}><FileText size={12} /> Draft report (日本語)</button>
                <button className="text-blue-600" onClick={() => openDraft(a, 'en')}>Draft report (English)</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {limits && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-semibold text-slate-700">When alerts are raised</summary>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {LIMIT_LABELS.map(([k, label]) => (
              <label key={k} className="block text-xs font-bold text-slate-600">{label}
                <input className={`${input} mt-1 block w-full font-normal`} type="number" min={1} value={limits[k]} onChange={(e) => setLimits({ ...limits, [k]: Number(e.target.value) })} />
              </label>
            ))}
          </div>
          <button className="mt-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white" onClick={saveLimits}>Save the limits</button>
        </details>
      )}

      {deciding && (
        <Modal open onClose={() => setDeciding(null)} title={deciding.status === 'reviewed' ? 'Record what you found' : 'Why is this not a problem?'} size="md"
          footer={<><button type="button" onClick={() => setDeciding(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium">Cancel</button>
            <button type="button" disabled={!note.trim()} onClick={decide} className="auth-primary-btn w-auto px-5">Save</button></>}>
          <textarea className={`${input} w-full`} rows={4} aria-label="What you found" placeholder="For example: the careers teacher was preparing interviews for year 9" value={note} onChange={(e) => setNote(e.target.value)} />
        </Modal>
      )}
      {draft && (
        <Modal open onClose={() => setDraft(null)} title={draft.title} size="lg"
          footer={<><button type="button" onClick={() => setDraft(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium">Close</button>
            <button type="button" onClick={print} className="auth-primary-btn inline-flex w-auto items-center gap-1 px-5"><Printer size={14} /> Print</button></>}>
          <dl className="space-y-2 text-sm">
            {draft.sections.map((s) => <div key={s.heading}><dt className="font-semibold text-slate-800">{s.heading}</dt><dd className="text-slate-700">{s.text}</dd></div>)}
          </dl>
          <ul className="mt-3 list-disc pl-5 text-xs text-slate-600">{draft.guidance.map((g) => <li key={g}>{g}</li>)}</ul>
          <p className="mt-2 text-xs italic text-slate-500">{draft.note}</p>
        </Modal>
      )}
    </section>
  );
}
