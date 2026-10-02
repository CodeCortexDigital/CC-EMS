import { useCallback, useEffect, useMemo, useState } from 'react';
import { Mail, Network, Phone, Search } from 'lucide-react';
import { toast } from 'sonner';
import hr, { errorText, OrgNode, Person } from '@/services/hr.service';
import { card, Empty, input, PageHead, Pill, Spinner, useIsHr } from './ui';

function Node({ n, depth, onPick }: { n: OrgNode; depth: number; onPick: (p: Person) => void }) {
  return (
    <li>
      <button onClick={() => onPick(n)} className="text-left rounded-lg border border-slate-200 bg-white px-3 py-1.5 hover:border-emerald-400 mb-1">
        <span className="font-bold text-sm">{n.name}</span>
        <span className="text-xs text-slate-500 ml-2">{[n.role, n.department].filter(Boolean).join(' · ')}</span>
        {n.reports.length > 0 && <span className="text-xs text-emerald-700 ml-2">{n.reports.length} report{n.reports.length > 1 ? 's' : ''}</span>}
      </button>
      {n.reports.length > 0 && (
        <ul className={`ml-4 pl-4 border-l-2 ${depth % 2 ? 'border-slate-200' : 'border-emerald-200'} space-y-0.5`}>
          {n.reports.map((c) => <Node key={c.id} n={c} depth={depth + 1} onPick={onPick} />)}
        </ul>
      )}
    </li>
  );
}

export default function DirectoryPage() {
  const isHr = useIsHr();
  const [view, setView] = useState<'list' | 'chart'>('list');
  const [people, setPeople] = useState<Person[] | null>(null);
  const [tree, setTree] = useState<OrgNode[] | null>(null);
  const [q, setQ] = useState('');
  const [dept, setDept] = useState('');
  const [picked, setPicked] = useState<Person | null>(null);

  const load = useCallback(() => {
    hr.directory().then(setPeople).catch(() => setPeople([]));
    hr.orgChart().then((r) => setTree(r.tree)).catch(() => setTree([]));
  }, []);
  useEffect(load, [load]);

  const departments = useMemo(() => [...new Set((people || []).map((p) => p.department).filter(Boolean))].sort(), [people]);
  const shown = useMemo(() => (people || []).filter((p) =>
    (!dept || p.department === dept) && (!q.trim() || `${p.name} ${p.role} ${p.email} ${p.employee_id}`.toLowerCase().includes(q.trim().toLowerCase()))), [people, q, dept]);

  const setManager = async (p: Person, managerId: string) => {
    try { await hr.setManager(p.id, managerId || null); toast.success(managerId ? 'Reporting line saved.' : 'Reporting line removed.'); setPicked(null); load(); }
    catch (e) { toast.error(errorText(e, 'Could not change the reporting line.')); }
  };

  return (
    <div className="p-4 sm:p-6">
      <PageHead title="Staff directory" hint="Who works here, what they do and who they report to.">
        <div className="flex gap-2">
          {([['list', 'Directory'], ['chart', 'Org chart']] as const).map(([k, l]) => (
            <button key={k} onClick={() => setView(k)} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${view === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{k === 'chart' && <Network className="inline w-3.5 h-3.5 mr-1" />}{l}</button>
          ))}
        </div>
      </PageHead>

      {view === 'list' ? (
        <>
          <div className="flex flex-wrap gap-2 mb-3">
            <div className="relative flex-1 min-w-[14rem]"><Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" /><input aria-label="Search staff" className={`${input} pl-9`} placeholder="Search by name, role or email" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <select aria-label="Department" className={`${input} max-w-[14rem]`} value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">All departments</option>{departments.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          {people === null ? <Spinner /> : shown.length === 0 ? <Empty>No staff match.</Empty> : (
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {shown.map((p) => (
                <div key={p.id} className={card}>
                  <div className="flex items-start gap-2">
                    <div className="mr-auto min-w-0">
                      <p className="font-bold truncate">{p.name}</p>
                      <p className="text-xs text-slate-500">{[p.role, p.department].filter(Boolean).join(' · ') || 'No role set'}</p>
                    </div>
                    {p.teacher_type === 'relief' && <Pill tone="blue">relief</Pill>}
                  </div>
                  <p className="text-xs text-slate-600 mt-2 flex items-center gap-1 truncate"><Mail className="w-3 h-3" />{p.email}</p>
                  {p.phone && <p className="text-xs text-slate-600 flex items-center gap-1"><Phone className="w-3 h-3" />{p.phone}</p>}
                  <p className="text-xs text-slate-500 mt-2">Reports to: <span className="font-semibold text-slate-700">{p.manager_name || 'nobody set'}</span></p>
                  {isHr && <button className="text-xs font-bold text-emerald-700 mt-2" onClick={() => setPicked(p)}>Change reporting line</button>}
                </div>
              ))}
            </div>
          )}
        </>
      ) : tree === null ? <Spinner /> : tree.length === 0 ? <Empty>No staff yet.</Empty> : (
        <div className={`${card} overflow-x-auto`}>
          {tree.length > 8 && tree.every((n) => n.reports.length === 0) && (
            <p className="text-xs text-amber-700 mb-3">Nobody has a manager set yet{isHr ? '; use "Change reporting line" in the Directory to build the chart.' : '.'}</p>
          )}
          <ul className="space-y-1">{tree.map((n) => <Node key={n.id} n={n} depth={0} onPick={(p) => isHr && setPicked(p)} />)}</ul>
        </div>
      )}

      {picked && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setPicked(null)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm space-y-3" onClick={(e) => e.stopPropagation()}>
            <h2 className="font-black">{picked.name} reports to</h2>
            <select aria-label="Manager" className={input} defaultValue={picked.manager_id || ''} onChange={(e) => setManager(picked, e.target.value)}>
              <option value="">Nobody (top of the chart)</option>
              {(people || []).filter((p) => p.id !== picked.id).map((p) => <option key={p.id} value={p.id}>{p.name}{p.role ? ` · ${p.role}` : ''}</option>)}
            </select>
            <button className="text-xs font-bold text-slate-600" onClick={() => setPicked(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
