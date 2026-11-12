import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';
import classService, { SchoolClass } from '@/services/class.service';
import termReports, { errorText, Layout, LayoutList, Scale, TermRoster } from '@/services/termReports.service';
import { btn, btnGhost, card, Empty, input, PageHead, Pill, Spinner } from '../hr/ui';

const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean);

/** Term reports (通知表): pick a class and a term, open a student's report. Administrators also edit the layout. */
export default function TermReportsPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [classId, setClassId] = useState('');
  const [termId, setTermId] = useState('');
  const [data, setData] = useState<TermRoster | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showLayout, setShowLayout] = useState(false);

  useEffect(() => { classService.getAll().then((r) => setClasses(r.data || [])).catch(() => setClasses([])); }, []);
  useEffect(() => {
    termReports.roster({ ...(classId ? { class: classId } : {}), ...(termId ? { term: termId } : {}) })
      .then((d) => { setData(d); if (!termId && d.terms[0]) setTermId(d.terms[0].id); })
      .catch((e) => { setData({ year: '', terms: [], results: [] }); toast.error(errorText(e, 'Could not load the students.')); });
  }, [classId, termId]);

  const open = async (student: string) => {
    setBusy(student);
    try { const r = await termReports.open(student, termId); navigate(`/education/term-reports/${r.id}`); }
    catch (e) { toast.error(errorText(e, 'Could not open the report.')); } finally { setBusy(null); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Term reports (通知表)" hint="Each student's report for a term, in your school's own layout: ratings by subject, behaviour, attendance and comments.">
        {isAdmin && <button className={btnGhost} onClick={() => setShowLayout(!showLayout)}>{showLayout ? 'Close the layout' : 'Edit the layout'}</button>}
      </PageHead>
      {showLayout && <LayoutEditor />}
      <div className={`${card} grid gap-3 sm:grid-cols-2`}>
        <label className="block text-xs font-bold text-slate-600">Class
          <select className={`${input} mt-1 font-normal`} value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">Choose a class</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="block text-xs font-bold text-slate-600">Term {data?.year ? `(${data.year})` : ''}
          <select className={`${input} mt-1 font-normal`} value={termId} onChange={(e) => setTermId(e.target.value)}>
            {(data?.terms || []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
      </div>
      <div className={`${card} overflow-x-auto`}>
        {data === null ? <Spinner /> : !classId ? <Empty>Choose a class to see its students.</Empty> : data.results.length === 0 ? <Empty>No students found.</Empty> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th className="py-2 pr-3">Student no.</th><th className="pr-3">Name</th><th className="pr-3">Report</th><th><span className="sr-only">Action</span></th></tr></thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.student} className="border-t border-slate-100">
                  <td className="py-2 pr-3 whitespace-nowrap">{r.student_number}</td>
                  <td className="pr-3 font-semibold">{r.student_name}</td>
                  <td className="pr-3">{r.is_locked ? <Pill tone="green">Finalised</Pill> : r.report_id ? <Pill tone="amber">In progress</Pill> : <Pill tone="slate">Not started</Pill>}</td>
                  <td className="text-right"><button className={btn} disabled={busy === r.student} onClick={() => open(r.student)}>{r.report_id ? 'Open report' : 'Start report'}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/** The layout of the report: administrators set the subjects, scale, behaviour items and comment boxes to match the school's own form. */
function LayoutEditor() {
  const [list, setList] = useState<LayoutList | null>(null);
  const [id, setId] = useState('');
  const [name, setName] = useState('');
  const [scale, setScale] = useState<Scale>('abc');
  const [viewpoints, setViewpoints] = useState(true);
  const [subjects, setSubjects] = useState('');
  const [conduct, setConduct] = useState('');
  const [boxes, setBoxes] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [sections, setSections] = useState({ attendance: true, conduct: true, comments: true });
  const [saving, setSaving] = useState(false);

  const pick = (layouts: Layout[], pickId: string) => {
    const l = layouts.find((x) => x.id === pickId) || layouts[0];
    if (!l) return;
    setId(l.id); setName(l.name); setScale(l.config.scale); setViewpoints(l.config.viewpoints); setSubjects(l.config.subjects.join('\n'));
    setConduct(l.config.conduct_items.join('\n')); setBoxes(l.config.comment_fields.map((c) => c.label).join('\n')); setIsDefault(l.is_default); setSections(l.config.sections);
  };
  useEffect(() => { termReports.layouts().then((d) => { setList(d); pick(d.layouts, ''); }).catch(() => toast.error('Could not load the layout.')); }, []);
  if (!list) return <div className={card}><Spinner /></div>;
  const current = list.layouts.find((l) => l.id === id);

  const save = async () => {
    if (!current) return;
    const used = new Set<string>();
    const comment_fields = lines(boxes).map((label, i) => {
      let key = current.config.comment_fields.find((c) => c.label === label)?.key || `box${i + 1}`;
      while (used.has(key)) key += 'x';
      used.add(key);
      return { key, label };
    });
    setSaving(true);
    try {
      const saved = await termReports.saveLayout({ id, name, level: current.level, is_default: isDefault,
        config: { ...current.config, scale, viewpoints, subjects: lines(subjects), conduct_items: lines(conduct), comment_fields, sections } });
      const next = list.layouts.map((l) => (l.id === saved.id ? saved : isDefault && l.level === saved.level ? { ...l, is_default: false } : l));
      setList({ ...list, layouts: next });
      toast.success('The layout was saved. Reports already started keep the layout they began with.');
    } catch (e) { toast.error(errorText(e, 'Could not save the layout.')); } finally { setSaving(false); }
  };

  return (
    <section className={`${card} space-y-3`} aria-label="Report layout">
      <h2 className="font-bold text-sm">Report layout</h2>
      <p className="text-xs text-slate-600">Match this to your school's own 通知表. One subject, behaviour item or comment box per line. Reports already started keep the layout they began with.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block text-xs font-bold text-slate-600">Layout
          <select className={`${input} mt-1 font-normal`} value={id} onChange={(e) => pick(list.layouts, e.target.value)}>
            {list.layouts.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </label>
        <label className="block text-xs font-bold text-slate-600">Name
          <input className={`${input} mt-1 font-normal`} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block text-xs font-bold text-slate-600">Rating scale
          <select className={`${input} mt-1 font-normal`} value={scale} onChange={(e) => setScale(e.target.value as Scale)}>
            {(Object.keys(list.scales) as Scale[]).map((k) => <option key={k} value={k}>{list.scales[k]}</option>)}
          </select>
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block text-xs font-bold text-slate-600">Subjects
          <textarea className={`${input} mt-1 font-normal`} rows={8} value={subjects} onChange={(e) => setSubjects(e.target.value)} />
        </label>
        <label className="block text-xs font-bold text-slate-600">Behaviour items
          <textarea className={`${input} mt-1 font-normal`} rows={8} value={conduct} onChange={(e) => setConduct(e.target.value)} />
        </label>
        <label className="block text-xs font-bold text-slate-600">Comment boxes
          <textarea className={`${input} mt-1 font-normal`} rows={8} value={boxes} onChange={(e) => setBoxes(e.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={viewpoints} onChange={(e) => setViewpoints(e.target.checked)} /> Show the three viewpoints for each subject</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={sections.attendance} onChange={(e) => setSections({ ...sections, attendance: e.target.checked })} /> Attendance</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={sections.conduct} onChange={(e) => setSections({ ...sections, conduct: e.target.checked })} /> Behaviour</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={sections.comments} onChange={(e) => setSections({ ...sections, comments: e.target.checked })} /> Comments</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} /> Use for new reports at this level</label>
      </div>
      <div><button className={btn} disabled={saving} onClick={save}>Save the layout</button></div>
    </section>
  );
}
