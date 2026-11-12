import { useEffect, useState } from 'react';
import { BookLock, Download, Pencil, Plus, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import privacy, { DataRegisterEntry, errorText } from '@/services/privacy.service';

const card = 'bg-white rounded-xl border border-slate-200 shadow-sm';
const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm';
const day = (d: string) => new Date(d).toLocaleDateString(undefined, { dateStyle: 'medium' } as any);
const blank = { name: '', data_items: '', purpose: '', how_collected: '', retention: '', shared_with: '', storage_location: '', sensitive: false, needs_consent: false };
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));

/** Security & privacy → Privacy → Data handling register (個人情報取扱台帳): what personal data the school holds, why, how it is
 *  collected, how long it is kept, who it is given to and where it is stored. Sensitive data (要配慮個人情報) is flagged.
 *  It is the first thing an education board or a parent asks to see. */
export default function DataRegister() {
  const [entries, setEntries] = useState<DataRegisterEntry[] | null>(null);
  const [school, setSchool] = useState('');
  const [editing, setEditing] = useState<(Partial<DataRegisterEntry> & typeof blank) | null>(null);
  const [busy, setBusy] = useState(false);
  const apply = (d: { entries: DataRegisterEntry[]; school: string }) => { setEntries(d.entries); setSchool(d.school); };
  useEffect(() => { privacy.register().then(apply).catch(() => setEntries([])); }, []);
  if (!entries) return null;
  const lang = document.documentElement.lang || 'en';

  const loadStarter = async () => {
    try { apply(await privacy.loadRegisterDefaults(lang)); toast.success('The standard list was added. Check each line and correct it for your school.'); }
    catch (e) { toast.error(errorText(e, 'Could not add the list.')); }
  };
  const save = async () => {
    if (!editing) return;
    setBusy(true);
    try { apply(await privacy.saveRegisterEntry(editing)); setEditing(null); toast.success('Saved.'); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setBusy(false); }
  };
  const remove = async () => {
    if (!editing?.id) return;
    try { apply(await privacy.deleteRegisterEntry(editing.id)); setEditing(null); }
    catch (e) { toast.error(errorText(e, 'Could not remove.')); }
  };
  const print = () => {
    const w = window.open('', '_blank');
    if (!w) { toast.error('Allow pop-ups to print.'); return; }
    const head = ['Name', 'Data', 'Purpose of use', 'How collected', 'Retention', 'Given to', 'Stored', 'Sensitive'];
    const body = entries.map((e) => `<tr><td>${esc(e.name)}</td><td>${esc(e.data_items)}</td><td>${esc(e.purpose)}</td><td>${esc(e.how_collected)}</td><td>${esc(e.retention)}</td><td>${esc(e.shared_with)}</td><td>${esc(e.storage_location)}</td><td>${e.sensitive ? '●' : ''}</td></tr>`).join('');
    w.document.write(`<!doctype html><html lang="${esc(lang)}"><meta charset="utf-8"><title>${esc(school)}</title><style>body{font:11px/1.4 sans-serif;margin:16px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #999;padding:4px;vertical-align:top;text-align:left}th{background:#eee}@page{size:A4 landscape}</style><h1 style="font-size:16px">${esc(school)}</h1><table><thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`);
    w.document.close(); w.focus(); w.print();
  };

  return (
    <section className={`${card} p-5`} aria-labelledby="register-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="register-title" className="flex items-center gap-2 font-bold text-slate-800"><BookLock size={16} /> Data handling register</h2>
        {entries.length > 0 && (
          <div className="flex gap-2">
            <button onClick={() => privacy.registerCsv()} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold"><Download size={13} /> CSV</button>
            <button onClick={print} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold"><Printer size={13} /> Print</button>
            <button onClick={() => setEditing({ ...blank })} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold"><Plus size={13} /> Add a line</button>
          </div>
        )}
      </div>
      <p className="mt-1 text-sm text-slate-600">What personal information the school holds, why, how it is collected, how long it is kept, who it is given to and where it is stored. Health, support and family information is marked as sensitive.</p>
      {entries.length === 0 ? (
        <div className="mt-3 rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600">
          <p>The register is empty. Start from the standard list for schools and correct it for your school.</p>
          <button onClick={loadStarter} className="auth-primary-btn mt-3 w-auto px-5">Add the standard list</button>
        </div>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100">
          {entries.map((e) => (
            <li key={e.id} className={`py-3 text-sm ${e.is_active ? '' : 'opacity-50'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-slate-800">{e.name}
                  {e.sensitive && <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-800">Sensitive</span>}
                  {e.needs_consent && <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Needs consent</span>}
                </span>
                <button onClick={() => setEditing({ ...e })} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600" aria-label={`Edit ${e.name}`}><Pencil size={12} /> Edit</button>
              </div>
              <dl className="mt-1 grid gap-x-4 gap-y-1 text-slate-600 sm:grid-cols-2">
                <div><dt className="inline font-medium text-slate-700">Data: </dt><dd className="inline">{e.data_items}</dd></div>
                <div><dt className="inline font-medium text-slate-700">Purpose of use: </dt><dd className="inline">{e.purpose}</dd></div>
                <div><dt className="inline font-medium text-slate-700">How collected: </dt><dd className="inline">{e.how_collected}</dd></div>
                <div><dt className="inline font-medium text-slate-700">Retention: </dt><dd className="inline">{e.retention}</dd></div>
                <div><dt className="inline font-medium text-slate-700">Given to: </dt><dd className="inline">{e.shared_with}</dd></div>
                <div><dt className="inline font-medium text-slate-700">Stored: </dt><dd className="inline">{e.storage_location}</dd></div>
              </dl>
              <p className="mt-1 text-[11px] text-slate-400">Last reviewed {day(e.reviewed_at)}{e.updated_by ? ` · ${e.updated_by}` : ''}</p>
            </li>
          ))}
        </ul>
      )}
      {editing && (
        <Modal open onClose={() => setEditing(null)} title={editing.id ? 'Edit this line' : 'Add a line'} size="lg"
          footer={<>
            {editing.id && <button type="button" onClick={remove} className="mr-auto rounded-lg border border-rose-300 px-3 py-2 text-sm font-medium text-rose-700">Remove</button>}
            <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium">Cancel</button>
            <button type="button" onClick={save} disabled={busy} className="auth-primary-btn w-auto px-5">Save</button></>}>
          <div className="space-y-2">
            <input className={input} aria-label="Name" placeholder="Name of the data, e.g. Health information" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <textarea className={input} rows={2} aria-label="Data" placeholder="What data it includes" value={editing.data_items} onChange={(e) => setEditing({ ...editing, data_items: e.target.value })} />
            <textarea className={input} rows={2} aria-label="Purpose of use" placeholder="Purpose of use: what it is used for" value={editing.purpose} onChange={(e) => setEditing({ ...editing, purpose: e.target.value })} />
            <textarea className={input} rows={2} aria-label="How collected" placeholder="How it is collected" value={editing.how_collected} onChange={(e) => setEditing({ ...editing, how_collected: e.target.value })} />
            <input className={input} aria-label="Retention" placeholder="How long it is kept" value={editing.retention} onChange={(e) => setEditing({ ...editing, retention: e.target.value })} />
            <textarea className={input} rows={2} aria-label="Given to" placeholder="Who it is given to" value={editing.shared_with} onChange={(e) => setEditing({ ...editing, shared_with: e.target.value })} />
            <input className={input} aria-label="Stored" placeholder="Where it is stored (country)" value={editing.storage_location} onChange={(e) => setEditing({ ...editing, storage_location: e.target.value })} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={editing.sensitive} onChange={(e) => setEditing({ ...editing, sensitive: e.target.checked })} /> Sensitive information (health, disability, family, guidance)</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={editing.needs_consent} onChange={(e) => setEditing({ ...editing, needs_consent: e.target.checked })} /> Needs the guardian's consent</label>
          </div>
        </Modal>
      )}
    </section>
  );
}
