// Small building blocks shared by the front desk, health office, safety, forms, admissions and settings screens.
// Same look as the Staff & HR pages.
import { Loader2 } from 'lucide-react';
import type { ReactNode } from 'react';
import OverflowTabs from './OverflowTabs';

export const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white';
export const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-5';
export const btn = 'px-3.5 py-2 rounded-lg text-sm font-medium bg-[var(--app-accent)] text-white shadow-sm hover:bg-[var(--app-accent-strong)] disabled:opacity-50';
export const btnGhost = 'px-3.5 py-2 rounded-lg text-sm font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50';
export const btnDanger = 'px-3.5 py-2 rounded-lg text-sm font-medium border border-rose-200 bg-white text-rose-700 hover:bg-rose-50 disabled:opacity-50';

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
    <div className="flex flex-wrap items-end gap-3 mb-3">
      <div className="mr-auto">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {hint && <p className="mt-0.5 text-sm text-slate-500 max-w-2xl">{hint}</p>}
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
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
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

/** Tabs inside a page (no router): underline tabs; any that do not fit go into a "More" menu. */
export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: Array<[T, string]> }) {
  return (
    <div className="flex mb-3 border-b border-slate-200">
      <OverflowTabs role="tab" ariaLabel="Tabs" items={tabs.map(([id, label]) => ({ id, label }))} activeId={value} onSelect={(id) => onChange(id as T)} />
    </div>
  );
}
