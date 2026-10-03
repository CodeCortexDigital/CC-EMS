// Type two letters of a name or a student number, pick the student. Used wherever staff work with one child.
import { useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import frontDesk, { StudentHit } from '@/services/frontdesk.service';
import { input } from './kit';

export default function StudentPicker({ onPick, label = 'Find a student', autoFocus = false }: {
  onPick: (s: StudentHit) => void; label?: string; autoFocus?: boolean;
}) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<StudentHit[]>([]);
  const [searched, setSearched] = useState(false);
  const latest = useRef(0);

  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) { setHits([]); setSearched(false); return; }
    const ticket = ++latest.current;
    const timer = window.setTimeout(() => {
      frontDesk.findStudents(text)
        .then((r) => { if (ticket === latest.current) { setHits(r); setSearched(true); } })
        .catch(() => { if (ticket === latest.current) { setHits([]); setSearched(true); } });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [q]);

  return (
    <div className="relative">
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
        <input aria-label={label} className={`${input} pl-9`} placeholder={`${label} (name or student number)`} value={q} autoFocus={autoFocus}
          onChange={(e) => setQ(e.target.value)} />
      </div>
      {hits.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-auto" role="listbox">
          {hits.map((s) => (
            <li key={s.id}>
              <button type="button" role="option" aria-selected={false} className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50"
                onClick={() => { onPick(s); setQ(''); setHits([]); setSearched(false); }}>
                <b>{s.name}</b> <span className="text-slate-400">{s.student_id}{s.class_name ? ` · ${s.class_name}` : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {searched && hits.length === 0 && <p className="text-xs text-slate-500 mt-1">No active student matches “{q.trim()}”.</p>}
    </div>
  );
}
