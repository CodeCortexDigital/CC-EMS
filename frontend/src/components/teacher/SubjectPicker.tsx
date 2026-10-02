import { useEffect, useState } from 'react';
import scheduling, { SubjectRef } from '@/services/scheduling.service';

/** Tick the subjects a teacher is qualified to teach. Controlled: the parent keeps the list of subject ids. */
export default function SubjectPicker({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const [subjects, setSubjects] = useState<SubjectRef[] | null>(null);
  useEffect(() => { scheduling.subjects().then(setSubjects).catch(() => setSubjects([])); }, []);

  if (subjects === null) return <p className="text-xs text-slate-400">Loading subjects…</p>;
  if (subjects.length === 0) return <p className="text-xs text-slate-500">No subjects set up yet. Add subjects under Academic Setup first.</p>;
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Subjects they teach">
      {subjects.map((s) => (
        <button key={s.id} type="button" aria-pressed={value.includes(s.id)} onClick={() => toggle(s.id)}
          className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${value.includes(s.id) ? 'bg-purple-600 border-purple-600 text-white' : 'border-slate-200 text-slate-600 bg-white'}`}>
          {s.name}
        </button>
      ))}
    </div>
  );
}
