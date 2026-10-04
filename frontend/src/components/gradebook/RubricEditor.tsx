// A scoring rubric for one assignment: criteria down the side, performance levels across. The teacher scores as usual;
// the rubric is a guide shown while grading and never changes a score.
import { useState } from 'react';
import { Loader2, Plus, Sparkles, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { btnGhost, errorText, input } from '@/components/common/kit';
import teacherAi, { DEFAULT_LEVELS, type Rubric } from '@/services/teacherAi.service';

export function RubricTable({ rubric }: { rubric: Rubric }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead><tr><th className="text-left p-2 border border-slate-200 bg-slate-50">Criterion</th>
          {rubric[0]?.levels.map((l) => <th key={l.label} className="text-left p-2 border border-slate-200 bg-slate-50">{l.label}</th>)}</tr></thead>
        <tbody>{rubric.map((c) => (
          <tr key={c.name}><td className="p-2 border border-slate-200 font-semibold align-top">{c.name}</td>
            {c.levels.map((l) => <td key={l.label} className="p-2 border border-slate-200 align-top">{l.description}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

export default function RubricEditor({ value, onChange, context }: {
  value: Rubric; onChange: (r: Rubric) => void;
  context: { title: string; instructions: string; subject: string; grade: string };
}) {
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<'ai' | 'template' | null>(null);

  const draft = async () => {
    if (!context.title.trim()) return toast.error('Give the assignment a title first.');
    if (value.length && !window.confirm('Replace the rubric you have with a new draft?')) return;
    setBusy(true);
    try {
      const r = await teacherAi.rubric({ ...context });
      onChange(r.criteria);
      setSource(r.source);
    } catch (e) { toast.error(errorText(e, 'Could not draft a rubric.')); } finally { setBusy(false); }
  };
  const setCriterion = (i: number, patch: Partial<Rubric[number]>) => onChange(value.map((c, k) => (k === i ? { ...c, ...patch } : c)));
  const setLevel = (i: number, j: number, description: string) =>
    setCriterion(i, { levels: value[i].levels.map((l, k) => (k === j ? { ...l, description } : l)) });
  const addCriterion = () => onChange([...value, { name: '', levels: (value[0]?.levels.map((l) => l.label) || DEFAULT_LEVELS).map((label) => ({ label, description: '' })) }]);

  return (
    <section aria-label="Rubric" className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div><h4 className="text-xs font-semibold text-slate-600">Rubric (optional)</h4>
          <p className="text-[11px] text-slate-500">A guide to show while grading. It does not change scores.</p></div>
        <button type="button" onClick={draft} disabled={busy} className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:underline disabled:opacity-50">
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Draft with AI
        </button>
      </div>
      {source && <p className="text-[11px] text-slate-600">{source === 'ai' ? 'Drafted by AI. Read it and edit it before you save.' : 'A blank outline (AI is not set up). Fill in what each level looks like.'}</p>}
      {value.map((c, i) => (
        <div key={i} className="rounded-lg border border-slate-200 p-2 space-y-1.5">
          <div className="flex gap-2">
            <input aria-label={`Criterion ${i + 1} name`} className={input} placeholder="What is being assessed" value={c.name} onChange={(e) => setCriterion(i, { name: e.target.value })} />
            <button type="button" aria-label={`Remove criterion ${i + 1}`} className="text-slate-400 hover:text-rose-600" onClick={() => onChange(value.filter((_, k) => k !== i))}><Trash2 className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {c.levels.map((l, j) => (
              <label key={l.label} className="text-[11px] font-semibold text-slate-600">{l.label}
                <textarea aria-label={`Criterion ${i + 1}, ${l.label}`} rows={2} className={input} value={l.description} onChange={(e) => setLevel(i, j, e.target.value)} />
              </label>
            ))}
          </div>
        </div>
      ))}
      <button type="button" className={btnGhost} onClick={addCriterion} disabled={value.length >= 8}><Plus className="inline w-3.5 h-3.5 mr-1" />Add a criterion</button>
      {value.length === 0 && <p className="text-xs text-slate-500">No rubric yet. Draft one with AI or add criteria yourself.</p>}
    </section>
  );
}
