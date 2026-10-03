// Small building blocks shared by the front desk, health office, safety, forms, admissions and settings screens.
// Same look as the Staff & HR pages.
import { Loader2 } from 'lucide-react';
import type { ReactNode } from 'react';

export const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white';
export const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-4';
export const btn = 'px-3 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50';
export const btnGhost = 'px-3 py-2 rounded-lg text-xs font-bold border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50';
export const btnDanger = 'px-3 py-2 rounded-lg text-xs font-bold border border-rose-300 text-rose-700 hover:bg-rose-50 disabled:opacity-50';

export const todayStr = () => new Date().toISOString().slice(0, 10);
export const fmtDate = (iso?: string | null) =>
  iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : '';
export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString([], { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '';
/** For a datetime-local input: the current local time as YYYY-MM-DDTHH:mm. */
export const nowLocal = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

export function Spinner() {
  return <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-500 py-8 text-center">{children}</p>;
}

export function PageHead({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div className="mr-auto">
        <h1 className="text-xl font-black text-slate-900">{title}</h1>
        {hint && <p className="text-sm text-slate-500 max-w-2xl">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

export function Pill({ tone, children }: { tone: 'green' | 'amber' | 'red' | 'blue' | 'slate'; children: ReactNode }) {
  const tones = {
    green: 'bg-emerald-100 text-emerald-800', amber: 'bg-amber-100 text-amber-800', red: 'bg-rose-100 text-rose-800',
    blue: 'bg-sky-100 text-sky-800', slate: 'bg-slate-100 text-slate-700',
  };
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${tones[tone]}`}>{children}</span>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-xs font-bold text-slate-600">
      {label}
      <div className="mt-1 font-normal">{children}</div>
    </label>
  );
}

/** The most useful message in an API error (our own `error` text, DRF `detail`, or the first field problem). */
export const errorText = (e: any, fallback: string): string => {
  const d = e?.response?.data;
  if (!d) return fallback;
  if (typeof d.error === 'string') return d.error;
  if (typeof d.detail === 'string') return d.detail;
  const first = typeof d === 'object' ? Object.values(d)[0] : null;
  if (Array.isArray(first) && typeof first[0] === 'string') return first[0];
  if (typeof first === 'string') return first;
  if (first && typeof first === 'object') return errorText({ response: { data: first } }, fallback);
  return fallback;
};

/** Tabs inside a page (no router): a row of pills. */
export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: Array<[T, string]> }) {
  return (
    <div className="flex flex-wrap gap-2 mb-4" role="tablist">
      {tabs.map(([key, label]) => (
        <button key={key} role="tab" aria-selected={value === key} onClick={() => onChange(key)}
          className={`px-3 py-1.5 rounded-full text-xs font-bold border ${value === key ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300 text-slate-700'}`}>
          {label}
        </button>
      ))}
    </div>
  );
}
