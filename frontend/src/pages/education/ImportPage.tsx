import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Copy, Download, FileArchive, FileSpreadsheet, History, Loader2, RefreshCw, Upload, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import imports, { errorText, ImportHistoryRow, ImportJob, ImportKind, Mode, PackKindResult, PackResult, RowState } from '@/services/imports.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm';
const STATE: Record<RowState, { label: string; tone: string; icon: typeof CheckCircle2 }> = {
  ready: { label: 'New', tone: 'bg-emerald-100 text-emerald-700', icon: CheckCircle2 },
  update: { label: 'Update', tone: 'bg-sky-100 text-sky-700', icon: RefreshCw },
  duplicate: { label: 'Already exists', tone: 'bg-slate-100 text-slate-600', icon: Copy },
  error: { label: 'Needs fixing', tone: 'bg-rose-100 text-rose-700', icon: XCircle },
};
const MODES: Array<{ id: Mode; title: string; text: string }> = [
  { id: 'add', title: 'Add only', text: 'New records are added. Anything that already exists is left alone.' },
  { id: 'update', title: 'Add and update', text: 'New records are added and existing ones are updated. Empty cells never erase what is there.' },
  { id: 'restore', title: 'Restore', text: 'For an empty school, for example after exporting and starting again. Everything in the pack is loaded.' },
];

type Tab = 'load' | 'download' | 'history';

/** Data: load a whole-school pack (or one file), download your data in the same layout, and see what was loaded before. */
export default function ImportPage() {
  const [tab, setTab] = useState<Tab>('load');
  const [kinds, setKinds] = useState<ImportKind[]>([]);
  const [history, setHistory] = useState<ImportHistoryRow[]>([]);
  const loadHistory = () => imports.history().then(setHistory).catch(() => undefined);
  const loadKinds = () => imports.kinds().then((d) => setKinds(d.kinds)).catch((e) => toast.error(errorText(e, 'Could not load.')));
  useEffect(() => { loadKinds(); loadHistory(); }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-800 flex items-center gap-2"><FileSpreadsheet className="w-5 h-5 text-brand" /> Data: import, export and restore</h1>
        <p className="text-sm text-slate-500 max-w-3xl">
          Your school's data lives in one set of CSV files, a <b>data pack</b>. The same files load data in, and come out when you export, so you can
          move a school, restore it, or start from the sample school.
        </p>
      </div>
      <div className="flex gap-2" role="tablist">
        {([['load', 'Load data', Upload], ['download', 'Download', Download], ['history', 'History', History]] as const).map(([id, label, Icon]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold border ${tab === id ? 'bg-brand text-white border-transparent' : 'border-slate-300 text-slate-700 bg-white'}`}>
            <Icon size={15} />{label}
          </button>
        ))}
      </div>
      {tab === 'load' && <LoadTab kinds={kinds} onLoaded={() => { loadKinds(); loadHistory(); }} />}
      {tab === 'download' && <DownloadTab kinds={kinds} />}
      {tab === 'history' && <HistoryTab rows={history} />}
    </div>
  );
}

function Pill({ state, n }: { state: RowState; n?: number }) {
  const s = STATE[state];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${s.tone}`}><s.icon size={12} />{n !== undefined ? `${n} ` : ''}{s.label.toLowerCase()}</span>;
}

function LoadTab({ kinds, onLoaded }: { kinds: ImportKind[]; onLoaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<Mode>('add');
  const [kind, setKind] = useState('');
  const [result, setResult] = useState<PackResult | null>(null);
  const [busy, setBusy] = useState<'' | 'check' | 'import'>('');
  const [job, setJob] = useState<ImportJob | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const isZip = !!file && file.name.toLowerCase().endsWith('.zip');
  const needsKind = !!file && !isZip;

  const reset = () => { setFile(null); setResult(null); setKind(''); if (input.current) input.current.value = ''; };
  const check = async (f: File, m: Mode, k: string) => {
    setBusy('check'); setResult(null);
    try { setResult(await imports.previewPack(f, m, f.name.toLowerCase().endsWith('.zip') ? undefined : k || undefined, setJob)); }
    catch (e) { toast.error(errorText(e, 'Could not read the file.')); } finally { setBusy(''); setJob(null); }
  };
  const pick = (f: File | null) => {
    setFile(f); setResult(null);
    if (f && f.name.toLowerCase().endsWith('.zip')) check(f, mode, '');
  };
  const run = async () => {
    if (!file) return;
    if (mode === 'restore' && !window.confirm('Restore loads everything in this pack into the school. Continue?')) return;
    setBusy('import');
    try {
      const r = await imports.importPack(file, mode, isZip ? undefined : kind || undefined, setJob);
      setResult(r);
      const t = r.totals;
      toast.success(`${t.ready} added${t.update ? `, ${t.update} updated` : ''}${t.duplicate ? `, ${t.duplicate} already there` : ''}${t.error ? `, ${t.error} with problems` : ''}.`);
      onLoaded();
    } catch (e) { toast.error(errorText(e, 'Could not import.')); } finally { setBusy(''); setJob(null); }
  };

  const totals = result?.totals;
  const canImport = !!result && !result.committed && (totals?.ready || 0) + (totals?.update || 0) > 0;

  return (
    <div className="space-y-4">
      <section className={`${card} p-5 space-y-4`}>
        <div className="grid md:grid-cols-3 gap-2" role="radiogroup" aria-label="What to do with records that already exist">
          {MODES.map((m) => (
            <label key={m.id} className={`rounded-lg border p-3 cursor-pointer ${mode === m.id ? 'border-brand ring-1 ring-brand' : 'border-slate-200'}`}>
              <input type="radio" name="mode" className="mr-2" checked={mode === m.id}
                onChange={() => { setMode(m.id); if (file && (isZip || kind)) check(file, m.id, kind); }} />
              <b className="text-sm text-slate-800">{m.title}</b>
              <p className="text-xs text-slate-500 mt-1">{m.text}</p>
            </label>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input ref={input} type="file" accept=".zip,.csv,.xlsx,.xlsm" aria-label="Data pack or file" className="text-sm"
            onChange={(e) => pick(e.target.files?.[0] || null)} />
          {needsKind && (
            <select aria-label="What this file holds" value={kind} onChange={(e) => { setKind(e.target.value); if (file && e.target.value) check(file, mode, e.target.value); }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">What does this file hold?</option>
              {kinds.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
            </select>
          )}
          {busy === 'check' && <span className="text-sm text-slate-500 inline-flex items-center gap-1"><Loader2 className="animate-spin" size={14} /> Checking…</span>}
          {job && job.status === 'running' && (
            <span className="text-sm text-slate-600 inline-flex items-center gap-2" role="status">
              <Loader2 className="animate-spin" size={14} />
              {job.commit ? 'Loading' : 'Checking'} {job.current || 'files'}… {job.files_done} of {job.total_files} files. Large files take a few minutes; you can keep this page open.
            </span>
          )}
          {file && <button onClick={reset} className="text-sm text-slate-500 underline">Clear</button>}
        </div>
        <p className="text-xs text-slate-500">
          Upload a <b>.zip pack</b> (several files at once, loaded in the right order) or a single CSV/Excel file. Nothing is saved until you press Import.
          Need a starting point? Open the Download tab for a blank pack.
        </p>
      </section>

      {result && (
        <section className={`${card} p-5 space-y-3`} aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-bold text-slate-800 mr-2">{result.committed ? 'Loaded' : 'Preview'}: {result.file}</h2>
            <Pill state="ready" n={totals!.ready} />{mode !== 'add' && <Pill state="update" n={totals!.update} />}
            <Pill state="duplicate" n={totals!.duplicate} /><Pill state="error" n={totals!.error} />
            {canImport && (
              <button onClick={run} disabled={busy === 'import'} className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                {busy === 'import' ? <Loader2 className="animate-spin" size={14} /> : <Upload size={14} />} Import {totals!.ready + totals!.update} records
              </button>
            )}
          </div>
          {result.unknown_files.length > 0 && <p className="text-xs text-amber-700 flex items-center gap-1"><AlertTriangle size={13} />Not recognised, so skipped: {result.unknown_files.join(', ')}</p>}
          <div className="space-y-2">
            {result.kinds.map((k) => <KindResult key={k.kind} k={k} committed={result.committed} />)}
          </div>
        </section>
      )}
    </div>
  );
}

function KindResult({ k, committed }: { k: PackKindResult; committed: boolean }) {
  const bad = (k.summary?.error || 0) > 0 || !!k.error;
  const [open, setOpen] = useState(bad);
  const [show, setShow] = useState<'all' | RowState>(bad ? 'error' : 'all');
  const rows = useMemo(() => (k.rows || []).filter((r) => show === 'all' || r.state === show), [k.rows, show]);
  return (
    <div className={`rounded-lg border ${bad ? 'border-rose-200' : 'border-slate-200'}`}>
      <button className="w-full flex flex-wrap items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        <span className="font-semibold text-sm text-slate-800">{k.label}</span><span className="text-xs text-slate-400">{k.file}</span>
        {k.summary && <span className="ml-auto flex gap-1.5">
          {k.summary.ready > 0 && <Pill state="ready" n={k.summary.ready} />}{k.summary.update > 0 && <Pill state="update" n={k.summary.update} />}
          {k.summary.duplicate > 0 && <Pill state="duplicate" n={k.summary.duplicate} />}{k.summary.error > 0 && <Pill state="error" n={k.summary.error} />}
        </span>}
        {committed && k.run_id && k.summary && k.summary.error > 0 && (
          <span role="link" tabIndex={0} className="text-xs underline text-slate-600" onClick={(e) => { e.stopPropagation(); imports.problems(k.run_id!, k.kind).catch(() => toast.error('Could not download.')); }}>
            Download problems
          </span>
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          {k.error && <p className="text-sm text-rose-700">{k.error}</p>}
          {(k.unknown_columns?.length || 0) > 0 && <p className="text-xs text-amber-700">Columns not used: {k.unknown_columns!.join(', ')}</p>}
          {k.summary && (
            <div className="flex gap-1.5 text-xs">
              {(['all', 'error', 'update', 'ready', 'duplicate'] as const).map((s) => (
                <button key={s} onClick={() => setShow(s)} className={`rounded-full px-2.5 py-1 border ${show === s ? 'bg-slate-800 text-white border-slate-800' : 'border-slate-300 text-slate-600'}`}>
                  {s === 'all' ? 'All shown' : STATE[s].label}
                </button>
              ))}
            </div>
          )}
          {rows.length > 0 && (
            <div className="overflow-x-auto border border-slate-100 rounded-lg">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50 text-slate-500"><tr><th className="px-2 py-1.5 text-left">Row</th><th className="px-2 py-1.5 text-left">Result</th>
                  {(k.columns || []).slice(0, 4).map((c) => <th key={c.key} className="px-2 py-1.5 text-left">{c.label}</th>)}<th className="px-2 py-1.5 text-left">Note</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.row} className="border-t border-slate-100 align-top">
                      <td className="px-2 py-1.5">{r.row}</td><td className="px-2 py-1.5"><Pill state={r.state} /></td>
                      {(k.columns || []).slice(0, 4).map((c) => <td key={c.key} className="px-2 py-1.5">{r.values[c.key]}</td>)}
                      <td className="px-2 py-1.5 text-slate-600">{r.messages.length ? r.messages.join('; ') : r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {k.truncated && <p className="text-xs text-slate-400">Showing every problem and the first 25 good rows.</p>}
        </div>
      )}
    </div>
  );
}

function DownloadTab({ kinds }: { kinds: ImportKind[] }) {
  const [busy, setBusy] = useState('');
  const run = async (id: string, fn: () => Promise<unknown>) => { setBusy(id); try { await fn(); } catch (e) { toast.error(errorText(e, 'Could not download.')); } finally { setBusy(''); } };
  const byTier = (t: number) => kinds.filter((k) => (k.tier || 1) === t);
  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-3">
        <section className={`${card} p-5 space-y-2`}>
          <h2 className="font-bold text-slate-800 flex items-center gap-2"><FileArchive size={17} /> Export my school</h2>
          <p className="text-sm text-slate-600">Every kind of record below, in one zip of CSV files. Upload it again with <b>Restore</b> to rebuild the school, or edit a file and load it with <b>Add and update</b>.</p>
          <button onClick={() => run('export', () => imports.packExport())} disabled={!!busy} className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {busy === 'export' ? <Loader2 className="animate-spin" size={14} /> : <Download size={14} />} Download data pack
          </button>
          <p className="text-xs text-slate-400">For a complete copy including audit logs and uploaded files, use Settings &gt; Security &gt; Data.</p>
        </section>
        <section className={`${card} p-5 space-y-2`}>
          <h2 className="font-bold text-slate-800 flex items-center gap-2"><FileArchive size={17} /> Blank pack</h2>
          <p className="text-sm text-slate-600">Every file with its headings and one example row, plus a README that lists the order to fill them in. Delete the example rows and add your own.</p>
          <button onClick={() => run('template', () => imports.packTemplate())} disabled={!!busy} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60">
            {busy === 'template' ? <Loader2 className="animate-spin" size={14} /> : <Download size={14} />} Download blank pack
          </button>
        </section>
      </div>
      {[1, 2].map((t) => byTier(t).length > 0 && (
        <section key={t} className={`${card} p-5`}>
          <h2 className="font-bold text-slate-800 mb-2">{t === 1 ? 'Set-up and records' : 'During the year'}</h2>
          <div className="divide-y divide-slate-100">
            {byTier(t).map((k) => (
              <div key={k.kind} className="py-2 flex flex-wrap items-center gap-2">
                <div className="mr-auto max-w-2xl">
                  <p className="text-sm font-semibold text-slate-800">{k.label} <span className="text-xs font-normal text-slate-400">{k.file}</span></p>
                  <p className="text-xs text-slate-500">{k.help}</p>
                  {k.depends.length > 0 && <p className="text-[11px] text-slate-400">Needs: {k.depends.join(', ')}</p>}
                </div>
                <button onClick={() => run(`t-${k.kind}`, () => imports.template(k.kind))} className="text-xs font-semibold text-slate-700 underline">Template</button>
                {k.can_export && <button onClick={() => run(`e-${k.kind}`, () => imports.exportKind(k.kind, k.file))} className="text-xs font-semibold text-slate-700 underline">Export</button>}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function HistoryTab({ rows }: { rows: ImportHistoryRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500 py-8 text-center">Nothing has been imported yet.</p>;
  return (
    <section className={`${card} overflow-x-auto`}>
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500"><tr>
          {['When', 'What', 'File', 'Mode', 'By', 'Added', 'Updated', 'Existed', 'Problems', ''].map((h) => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-100">
              <td className="px-3 py-2 whitespace-nowrap">{new Date(r.when).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
              <td className="px-3 py-2">{r.label}</td><td className="px-3 py-2 text-slate-500">{r.file}</td><td className="px-3 py-2">{r.mode}</td><td className="px-3 py-2">{r.by}</td>
              <td className="px-3 py-2">{r.added}</td><td className="px-3 py-2">{r.updated}</td><td className="px-3 py-2">{r.skipped}</td><td className="px-3 py-2">{r.failed}</td>
              <td className="px-3 py-2">{r.has_problems && <button className="text-xs underline" onClick={() => imports.problems(r.id, r.kind).catch(() => toast.error('Could not download.'))}>Problems</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
