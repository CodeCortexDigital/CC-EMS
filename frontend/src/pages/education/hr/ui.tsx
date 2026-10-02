// Small shared pieces for the Staff & HR pages.
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import hr, { Person } from '@/services/hr.service';
import { useAuth } from '@/hooks/useAuth';

export const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white';
export const card = 'bg-white rounded-xl border border-slate-200 shadow-sm p-4';
export const btn = 'px-3 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50';
export const btnGhost = 'px-3 py-2 rounded-lg text-xs font-bold border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50';
export const btnDanger = 'px-3 py-2 rounded-lg text-xs font-bold border border-rose-300 text-rose-700 hover:bg-rose-50 disabled:opacity-50';

/** Administrators, HR and managers manage staff records; everyone else sees their own. */
export function useIsHr() {
  const { role } = useAuth();
  return ['admin', 'hr', 'manager', 'superuser'].includes(String(role || '').toLowerCase());
}

/** Pay is for administrators and the HR role only. */
export function useIsPayroll() {
  const { role } = useAuth();
  return ['admin', 'hr', 'superuser'].includes(String(role || '').toLowerCase());
}

export const todayStr = () => new Date().toISOString().slice(0, 10);
export const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};
export const fmtDate = (iso?: string | null) =>
  iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : '';

export function Spinner() {
  return <div className="py-10 flex justify-center"><Loader2 className="animate-spin text-slate-400" /></div>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-slate-500 py-8 text-center">{children}</p>;
}

export function PageHead({ title, hint, children }: { title: string; hint?: string; children?: React.ReactNode }) {
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

export function Pill({ tone, children }: { tone: 'green' | 'amber' | 'red' | 'blue' | 'slate'; children: React.ReactNode }) {
  const tones = {
    green: 'bg-emerald-100 text-emerald-800', amber: 'bg-amber-100 text-amber-800', red: 'bg-rose-100 text-rose-800',
    blue: 'bg-sky-100 text-sky-800', slate: 'bg-slate-100 text-slate-700',
  };
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${tones[tone]}`}>{children}</span>;
}

/** The active staff list, loaded once (used to pick a person). */
export function useStaff() {
  const [staff, setStaff] = useState<Person[]>([]);
  useEffect(() => {
    hr.directory().then(setStaff).catch(() => setStaff([]));
  }, []);
  return staff;
}

export function StaffSelect({ value, onChange, staff, placeholder = 'Choose a person', label }: {
  value: string; onChange: (id: string) => void; staff: Person[]; placeholder?: string; label: string;
}) {
  return (
    <select aria-label={label} className={input} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder}</option>
      {staff.map((p) => <option key={p.id} value={p.id}>{p.name}{p.role ? ` · ${p.role}` : ''}</option>)}
    </select>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-bold text-slate-600">
      {label}
      <div className="mt-1 font-normal">{children}</div>
    </label>
  );
}
