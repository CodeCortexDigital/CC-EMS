import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import standards, { errorText, ExternalIdList, ExternalIdRow } from '@/services/standards.service';
import { btn, btnGhost, card, Empty, input, PageHead, Pill, Spinner } from '../hr/ui';

/** MEXT education data standards (administrators): the school's MEXT school code, and the IDs other systems use for our students and teachers. */
export default function MextStandardsPage() {
  const [code, setCode] = useState<string | null>(null);
  const [saved, setSaved] = useState('');
  const [system, setSystem] = useState('');
  const [csv, setCsv] = useState('');
  const [list, setList] = useState<ExternalIdList | null>(null);
  const [errors, setErrors] = useState<Array<{ row: number; message: string }>>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { standards.get().then((d) => { setCode(d.school_code); setSaved(d.school_code); }).catch(() => setCode('')); }, []);
  useEffect(() => { standards.ids(system.trim() || undefined).then(setList).catch(() => setList({ results: [], systems: [] })); }, [system]);

  const saveCode = async () => {
    try { const r = await standards.saveSchoolCode(code || ''); setCode(r.school_code); setSaved(r.school_code); toast.success('The school code was saved.'); }
    catch (e) { toast.error(errorText(e, 'Could not save the code.')); }
  };
  const importIds = async () => {
    setBusy(true); setErrors([]);
    try {
      const r = await standards.importCsv(system.trim(), csv);
      setList(r); setErrors(r.errors || []);
      toast[(r.errors || []).length ? 'error' : 'success'](`${r.saved} saved${(r.errors || []).length ? `, ${(r.errors || []).length} not saved` : ''}.`);
      if (!(r.errors || []).length) setCsv('');
    } catch (e) { toast.error(errorText(e, 'Could not import.')); } finally { setBusy(false); }
  };
  const remove = async (row: ExternalIdRow) => { try { setList(await standards.remove(row.id, system.trim() || undefined)); } catch (e) { toast.error(errorText(e, 'Could not remove.')); } };

  if (code === null) return <div className="p-6"><Spinner /></div>;
  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="MEXT standards" hint="The school code and the IDs other systems use, so data can be matched by ID instead of by name. The curriculum code of each subject is set on the Subjects page." />

      <section className={card} aria-label="MEXT school code">
        <h2 className="font-bold text-sm mb-1">MEXT school code (学校コード)</h2>
        <p className="text-xs text-slate-600 mb-2">A letter and twelve digits, for example B113110000012. Only the shape is checked here, not whether it is on MEXT's list.</p>
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${input} w-64 font-mono`} aria-label="School code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="B113110000012" />
          <button className={btn} disabled={code === saved} onClick={saveCode}>Save the code</button>
          {saved && code === saved && <Pill tone="green">Saved</Pill>}
        </div>
      </section>

      <section className={`${card} space-y-3`} aria-label="IDs in other systems">
        <h2 className="font-bold text-sm">IDs in other systems</h2>
        <p className="text-xs text-slate-600">Name the other system (for example the board of education's school-affairs system), then paste rows of <b>kind, our ID, their ID</b>. Kind is student or teacher; our ID is the student number or the employee ID. A person's ID in that system is replaced when you import it again.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs font-bold text-slate-600">System
            <input className={`${input} mt-1 font-normal`} list="systems" value={system} onChange={(e) => setSystem(e.target.value)} placeholder="e.g. 教育委員会 校務支援システム" />
            <datalist id="systems">{(list?.systems || []).map((s) => <option key={s} value={s} />)}</datalist>
          </label>
          <label className="block text-xs font-bold text-slate-600">Rows (CSV)
            <textarea className={`${input} mt-1 font-mono font-normal`} rows={4} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={'student,WKG-0001,S-123456\nteacher,T-100,K-9'} />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className={btn} disabled={busy || !system.trim() || !csv.trim()} onClick={importIds}>Import</button>
          <button className={btnGhost} onClick={() => standards.exportCsv(system.trim() || undefined).catch((e) => toast.error(errorText(e, 'Could not export.')))}>Export (CSV)</button>
        </div>
        {errors.length > 0 && (
          <ul role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {errors.map((e) => <li key={e.row}>Row {e.row}: {e.message}</li>)}
          </ul>
        )}
        {list === null ? <Spinner /> : list.results.length === 0 ? <Empty>No IDs saved{system.trim() ? ' for this system' : ''} yet.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="py-2 pr-3">Kind</th><th className="pr-3">Our ID</th><th className="pr-3">Name</th><th className="pr-3">System</th><th className="pr-3">Their ID</th><th><span className="sr-only">Action</span></th></tr></thead>
              <tbody>
                {list.results.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="py-1.5 pr-3">{r.kind === 'student' ? 'Student' : 'Teacher'}</td><td className="pr-3 font-mono">{r.local_id}</td><td className="pr-3">{r.name}</td>
                    <td className="pr-3">{r.system}</td><td className="pr-3 font-mono">{r.external_id}</td>
                    <td className="text-right"><button className="text-xs font-semibold text-rose-700" onClick={() => remove(r)} aria-label={`Remove ${r.external_id}`}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
