// Daily briefs (administrators only): the morning brief and the evening summary, drafted for review, approved by an administrator,
// rolled up weekly, fortnightly and monthly, and kept for about three months.
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, Loader2, Printer, RefreshCw, Sparkles, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { Empty, Pill, Spinner, Tabs, btn, btnDanger, btnGhost, card, errorText, fmtDate, fmtDateTime, input } from '@/components/common/kit';
import { formatMoney } from '@/utils/currency';
import briefs, {
  KIND_LABEL, PERIOD_LABEL, type Brief, type BriefSettings, type BriefSummary, type Item, type Kind, type Period, type Today,
} from '@/services/briefs.service';

// Where each figure's "open" link goes.
const ROUTES: Record<string, string> = {
  safety: '/education/safety', health: '/education/health-office', frontdesk: '/education/front-desk', hr: '/education/hr', cover: '/education/hr/cover',
  interventions: '/education/interventions', attendance: '/education/attendance', admissions: '/education/admissions', finance: '/education/fees/invoices',
  calendar: '/calendar', forms: '/education/forms', students: '/education/students', behaviour: '/education/behaviour',
};

const show = (i: Item) => (i.value == null ? 'not recorded' : i.unit === 'money' ? formatMoney(i.value) : i.unit === 'percent' ? `${i.value}%` : String(i.value));
const title = (b: BriefSummary) => (b.kind ? `${KIND_LABEL[b.kind]}, ${fmtDate(b.date)}` : `${PERIOD_LABEL[b.period as Period]} brief, ${fmtDate(b.period_start)} to ${fmtDate(b.period_end)}`);

const PRINT_CSS = `@media print { body * { visibility: hidden !important; } .brief-print, .brief-print * { visibility: visible !important; }
  .brief-print { position: absolute; left: 0; top: 0; width: 100%; } .no-print { display: none !important; } }`;

function ReadPill({ b }: { b: BriefSummary }) {
  return b.read_by_me ? null : <Pill tone="blue">Unread</Pill>;
}

function StatusPill({ b }: { b: BriefSummary }) {
  return b.status === 'approved'
    ? <Pill tone="green"><CheckCircle2 className="w-3 h-3 mr-1" />Approved{b.approved_by ? ` by ${b.approved_by}` : ''}</Pill>
    : <Pill tone="amber">Draft, not reviewed</Pill>;
}

/** One brief in full: the words (editable while a draft), what needs attention, every figure, and the approval controls. */
function BriefView({ brief, rollup, onChanged, onDeleted }: { brief: Brief; rollup?: boolean; onChanged: (b: Brief) => void; onDeleted: () => void }) {
  const [text, setText] = useState(brief.narrative);
  const [busy, setBusy] = useState('');
  const [headlines, setHeadlines] = useState(false);
  useEffect(() => setText(brief.narrative), [brief.id, brief.narrative]);
  const draft = brief.status === 'draft';
  const act = async (name: string, fn: () => Promise<Brief | void>, ok: string) => {
    setBusy(name);
    try { const r = await fn(); if (r) onChanged(r); toast.success(ok); } catch (e) { toast.error(errorText(e, 'That did not work.')); } finally { setBusy(''); }
  };
  const save = () => act('save', () => (rollup ? briefs.editRollup(brief.id, text) : briefs.edit(brief.id, text)), 'Saved');
  const approve = () => act('approve', () => (rollup ? briefs.approveRollup(brief.id, text) : briefs.approve(brief.id, text)), 'Approved');
  const markRead = () => act('read', () => (rollup ? briefs.markRollupRead(brief.id) : briefs.markRead(brief.id)), 'Marked as read');
  const remove = async () => {
    if (!window.confirm('Delete this for good?')) return;
    await act('delete', async () => { await (rollup ? briefs.removeRollup(brief.id) : briefs.remove(brief.id)); onDeleted(); }, 'Deleted');
  };

  return (
    <article className="brief-print space-y-3">
      <style>{PRINT_CSS}</style>
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="font-bold text-lg mr-2">{title(brief)}</h2>
        <StatusPill b={brief} />
        <Pill tone="slate">{brief.narrative_source === 'ai' ? 'Words written by AI' : 'Plain summary'}</Pill>
        {brief.edited && <Pill tone="blue">Edited</Pill>}
        <ReadPill b={brief} />
        <span className="ml-auto no-print">
          <button className={headlines ? btn : btnGhost} aria-pressed={headlines} onClick={() => setHeadlines(true)}>Headlines</button>{' '}
          <button className={!headlines ? btn : btnGhost} aria-pressed={!headlines} onClick={() => setHeadlines(false)}>Full detail</button>
        </span>
      </header>
      {brief.read_by.length > 0 && <p className="text-xs text-slate-500" aria-label="Read by">Read by {brief.read_by.map((r) => `${r.name} (${fmtDateTime(r.at)})`).join(', ')}</p>}
      {brief.status === 'approved' && <p className="text-xs text-slate-500">Approved {fmtDateTime(brief.approved_at)}. Locked: it can be printed or deleted, not changed.</p>}
      {rollup && <p className="text-xs text-slate-500">Worked out from {brief.days} daily brief{brief.days === 1 ? '' : 's'}{brief.approved_days != null ? ` (${brief.approved_days} approved)` : ''}.</p>}

      <section aria-label="Summary">
        {draft ? (
          <>
            <textarea aria-label="Summary text" rows={4} className={input} value={text} onChange={(e) => setText(e.target.value)} />
            <p className="text-[11px] text-slate-500 mt-1">
              {brief.narrative_source === 'ai' ? 'Written by AI from the figures below (counts only, no names). Read it against them, change anything you like, then approve.' : 'A plain summary of the figures below. Change anything you like, then approve.'}
            </p>
          </>
        ) : <p className="text-sm whitespace-pre-wrap">{brief.narrative}</p>}
      </section>

      {brief.attention.length > 0 && (
        <section aria-label="Needs attention" className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <h3 className="text-xs font-bold uppercase text-amber-900 mb-1">Needs attention</h3>
          <ul className="text-sm space-y-0.5">
            {brief.attention.map((a) => (
              <li key={a.key} className="flex gap-2"><b className="tabular-nums w-8 text-right">{a.value}</b><span className="flex-1">{a.label}</span>
                {ROUTES[a.link] && <Link to={ROUTES[a.link]} className="text-xs font-bold text-emerald-700 hover:underline no-print">Open</Link>}</li>
            ))}
          </ul>
        </section>
      )}

      {headlines && (
        <section aria-label="Headlines" className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {brief.headline.map((i) => (
            <div key={i.key} className={`rounded-xl border p-3 text-center ${i.attention ? 'border-amber-300 bg-amber-50' : 'border-slate-200'}`}>
              <div className="text-2xl font-extrabold tabular-nums">{show(i)}</div>
              <div className="text-[11px] text-slate-600 leading-tight mt-1">{i.label}</div>
            </div>
          ))}
          {brief.headline.length === 0 && <p className="col-span-full text-sm text-slate-500">No headline figures were recorded for this one.</p>}
        </section>
      )}

      {!headlines && <div className="grid sm:grid-cols-2 gap-3">
        {brief.sections.map(((s) => (
          <section key={s.key} aria-label={s.title} className="rounded-lg border border-slate-200 p-3">
            <h3 className="text-xs font-bold uppercase text-slate-500 mb-1">{s.title}</h3>
            <ul className="text-sm divide-y divide-slate-100">
              {s.items.map((i) => (
                <li key={i.key} className="py-1 flex gap-2 items-baseline">
                  <span className="flex-1">{i.label}</span>
                  <b className={`tabular-nums ${i.attention ? 'text-amber-700' : ''}`}>{show(i)}</b>
                </li>
              ))}
            </ul>
          </section>
        )))}
      </div>}

      <footer className="flex flex-wrap gap-2 pt-1 no-print">
        {draft && <button className={btn} disabled={!!busy} onClick={approve}>{busy === 'approve' ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="inline w-3.5 h-3.5 mr-1" />}Approve</button>}
        {draft && <button className={btnGhost} disabled={!!busy || text === brief.narrative} onClick={save}>Save my edits</button>}
        {!brief.read_by_me && <button className={btnGhost} disabled={!!busy} onClick={markRead}>Mark as read</button>}
        <button className={btnGhost} onClick={() => window.print()}><Printer className="inline w-3.5 h-3.5 mr-1" />Print</button>
        <button className={btnDanger} disabled={!!busy} onClick={remove}><Trash2 className="inline w-3.5 h-3.5 mr-1" />Delete</button>
      </footer>
    </article>
  );
}

function TodayCard({ kind, brief, onChange }: { kind: Kind; brief: Brief | null; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState<Brief | null>(brief);
  useEffect(() => setCurrent(brief), [brief]);
  const make = async () => {
    setBusy(true);
    try { setCurrent(await briefs.generate(kind)); onChange(); } catch (e) { toast.error(errorText(e, 'Could not prepare it.')); } finally { setBusy(false); }
  };
  return (
    <section className={card} aria-label={KIND_LABEL[kind]}>
      {current ? (
        <>
          <BriefView brief={current} onChanged={setCurrent} onDeleted={() => { setCurrent(null); onChange(); }} />
          {current.status === 'draft' && (
            <button className={`${btnGhost} mt-2`} disabled={busy} onClick={make} title="Replaces this draft with a fresh one">
              {busy ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="inline w-3.5 h-3.5 mr-1" />}Prepare again with the latest figures
            </button>
          )}
        </>
      ) : (
        <div className="text-center py-6 space-y-2">
          <h2 className="font-bold">{KIND_LABEL[kind]}</h2>
          <p className="text-sm text-slate-500">Not prepared yet today.</p>
          <button className={btn} disabled={busy} onClick={make}>{busy ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : <Sparkles className="inline w-3.5 h-3.5 mr-1" />}Prepare it now</button>
        </div>
      )}
    </section>
  );
}

function TodayTab() {
  const [d, setD] = useState<Today | null>(null);
  const load = useCallback(() => briefs.today().then(setD).catch((e) => toast.error(errorText(e, 'Could not load the briefs.'))), []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Spinner />;
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{fmtDate(d.date)} · school time ({d.time_zone}). Each starts as a draft: read it, edit if you wish, then approve.</p>
      <TodayCard kind="morning" brief={d.morning} onChange={load} />
      <TodayCard kind="evening" brief={d.evening} onChange={load} />
    </div>
  );
}

function ListTab({ rollups }: { rollups: boolean }) {
  const [kind, setKind] = useState<Kind | ''>('');
  const [period, setPeriod] = useState<Period | ''>('');
  const [rows, setRows] = useState<BriefSummary[] | null>(null);
  const [open, setOpen] = useState<Brief | null>(null);
  const [building, setBuilding] = useState('');
  const load = useCallback(() => {
    setRows(null);
    (rollups ? briefs.rollups(period || undefined) : briefs.list(kind || undefined)).then(setRows).catch(() => setRows([]));
  }, [rollups, kind, period]);
  useEffect(() => { load(); }, [load]);
  const view = async (id: string) => { try { setOpen(await (rollups ? briefs.rollup(id) : briefs.get(id))); } catch (e) { toast.error(errorText(e, 'Could not open it.')); } };
  const build = async (p: Period) => {
    setBuilding(p);
    try { const r = await briefs.buildRollup(p); toast.success('Built from the daily briefs. Review it, then approve.'); load(); setOpen(r); } catch (e) { toast.error(errorText(e, 'Could not build it.')); } finally { setBuilding(''); }
  };
  return (
    <div className="space-y-3">
      {rollups ? (
        <div className="flex flex-wrap gap-2 items-center">
          {(Object.keys(PERIOD_LABEL) as Period[]).map((p) => (
            <button key={p} className={btnGhost} disabled={!!building} onClick={() => build(p)}>{building === p ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : null}Build the latest {PERIOD_LABEL[p].toLowerCase()} brief</button>
          ))}
          <select aria-label="Show" className={`${input} w-auto`} value={period} onChange={(e) => setPeriod(e.target.value as Period | '')}>
            <option value="">All roll-ups</option>{(Object.keys(PERIOD_LABEL) as Period[]).map((p) => <option key={p} value={p}>{PERIOD_LABEL[p]}</option>)}
          </select>
        </div>
      ) : (
        <select aria-label="Show" className={`${input} w-auto`} value={kind} onChange={(e) => setKind(e.target.value as Kind | '')}>
          <option value="">Morning and evening</option><option value="morning">Morning briefs</option><option value="evening">Evening summaries</option>
        </select>
      )}
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty>{rollups ? 'No roll-ups yet. They are built from the daily briefs.' : 'No daily briefs are kept yet.'}</Empty> : (
        <ul className={`${card} divide-y divide-slate-100 p-0`}>
          {rows.map((b) => (
            <li key={b.id}>
              <button className="w-full text-left px-4 py-2.5 flex flex-wrap items-center gap-2 hover:bg-slate-50" onClick={() => view(b.id)}>
                <span className="font-semibold flex-1">{title(b)}</span>
                {b.attention_count > 0 && <Pill tone="amber">{b.attention_count} to look at</Pill>}
                <ReadPill b={b} />
                <StatusPill b={b} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && (
        <Modal open onClose={() => setOpen(null)} title={title(open)} size="xl">
          <BriefView brief={open} rollup={rollups} onChanged={(b) => { setOpen(b); load(); }} onDeleted={() => { setOpen(null); load(); }} />
        </Modal>
      )}
    </div>
  );
}

function SettingsTab() {
  const [s, setS] = useState<BriefSettings | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { briefs.settings().then(setS).catch(() => toast.error('Could not load the settings.')); }, []);
  if (!s) return <Spinner />;
  const save = async () => {
    setSaving(true);
    try { setS(await briefs.saveSettings({ enabled: s.enabled, morning_time: s.morning_time, evening_time: s.evening_time })); toast.success('Saved'); } catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <section className={`${card} space-y-3 max-w-xl`} aria-label="Brief settings">
      <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} /> Prepare the briefs automatically</label>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs font-bold text-slate-600">Morning brief ready at<input aria-label="Morning time" type="time" className={input} value={s.morning_time} onChange={(e) => setS({ ...s, morning_time: e.target.value })} /></label>
        <label className="text-xs font-bold text-slate-600">Evening summary ready at<input aria-label="Evening time" type="time" className={input} value={s.evening_time} onChange={(e) => setS({ ...s, evening_time: e.target.value })} /></label>
      </div>
      <p className="text-xs text-slate-500">Times are in your school&apos;s time zone (Settings, Language &amp; currency). They are always prepared as drafts for you to approve.</p>
      <p className="text-xs text-slate-500">Daily briefs and roll-ups are kept for {s.retention_days} days (about three months). Older ones are removed automatically, so the oldest are overwritten rather than piling up. You can print or delete any of them at any time.</p>
      <button className={btn} disabled={saving} onClick={save}>{saving ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : 'Save'}</button>
    </section>
  );
}

type TabKey = 'today' | 'history' | 'rollups' | 'settings';
const TABS: Array<[TabKey, string]> = [['today', 'Today'], ['history', 'Daily history'], ['rollups', 'Weekly, fortnightly, monthly'], ['settings', 'Settings']];

export default function BriefsPage() {
  const [tab, setTab] = useState<TabKey>('today');
  return (
    <div className="p-4 max-w-5xl mx-auto text-slate-800">
      <h1 className="text-xl font-bold">Daily briefs</h1>
      <p className="text-sm text-slate-500 mb-3">One page for the morning and one for the evening, instead of looking everywhere. Counts only, no names. Nothing is final until you approve it.</p>
      <Tabs value={tab} onChange={(v) => setTab(v as TabKey)} tabs={TABS} />
      {tab === 'today' && <TodayTab />}
      {tab === 'history' && <ListTab rollups={false} />}
      {tab === 'rollups' && <ListTab rollups />}
      {tab === 'settings' && <SettingsTab />}
    </div>
  );
}
