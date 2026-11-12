import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';
import classService, { SchoolClass } from '@/services/class.service';
import records, { errorText, LEVEL_LABEL, RosterRow } from '@/services/records.service';
import { btn, btnGhost, card, Empty, input, PageHead, Pill, Spinner } from '../hr/ui';

export default function RecordsPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [classId, setClassId] = useState('');
  const [search, setSearch] = useState('');
  const [rows, setRows] = useState<RosterRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    classService.getAll().then((r) => setClasses(r.data || [])).catch(() => setClasses([]));
  }, []);

  useEffect(() => {
    setRows(null);
    const t = setTimeout(() => {
      records.roster({ ...(classId ? { class: classId } : {}), ...(search.trim() ? { search: search.trim() } : {}) })
        .then(setRows).catch((e) => { setRows([]); toast.error(errorText(e, 'Could not load the students.')); });
    }, search ? 250 : 0);
    return () => clearTimeout(t);
  }, [classId, search]);

  const open = async (row: RosterRow) => {
    setBusy(row.student);
    try {
      const rec = await records.open(row.student);
      navigate(`/education/records/${rec.id}`);
    } catch (e) { toast.error(errorText(e, 'Could not open the record.')); } finally { setBusy(null); }
  };

  const exportCsv = async (all: boolean) => {
    try {
      await (all ? records.downloadCsv(null, { all: true }) : records.downloadCsv(null, { class: classId }));
    } catch (e) { toast.error(errorText(e, 'Could not export.')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Cumulative records (指導要録)" hint="The permanent record of each student, filled in year by year and sealed by the class teacher and the principal.">
        <button className={btnGhost} disabled={!classId} onClick={() => exportCsv(false)}>Export class (CSV)</button>
        {isAdmin && <button className={btnGhost} onClick={() => exportCsv(true)}>Export all (CSV)</button>}
        {isAdmin && <button className={btnGhost} onClick={() => navigate('/education/records/retention')}>Retention</button>}
      </PageHead>

      <div className={`${card} grid gap-3 sm:grid-cols-2`}>
        <label className="block text-xs font-bold text-slate-600">Class
          <select className={`${input} mt-1 font-normal`} value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">All classes</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="block text-xs font-bold text-slate-600">Search
          <input className={`${input} mt-1 font-normal`} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or student number" />
        </label>
      </div>

      <div className={`${card} overflow-x-auto`}>
        {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>No students found.</Empty> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-3">Student no.</th><th className="pr-3">Name</th><th className="pr-3">Class</th>
                <th className="pr-3">Level</th><th className="pr-3">Years entered / sealed</th><th><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.student} className="border-t border-slate-100">
                  <td className="py-2 pr-3 whitespace-nowrap">{r.student_number}</td>
                  <td className="pr-3 font-semibold">{r.student_name}</td>
                  <td className="pr-3 whitespace-nowrap">{r.class_name}</td>
                  <td className="pr-3"><Pill tone="blue">{LEVEL_LABEL[r.level]}</Pill></td>
                  <td className="pr-3 whitespace-nowrap">{r.years} / {r.years_sealed}</td>
                  <td className="text-right"><button className={btn} disabled={busy === r.student} onClick={() => open(r)}>Open record</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
