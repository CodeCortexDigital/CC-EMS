import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import hr, { Benefit, errorText, PayGrade, PayRow } from '@/services/hr.service';
import { formatMoney } from '@/utils/currency';
import { btn, btnGhost, card, Empty, Field, input, PageHead, Pill, Spinner, useIsPayroll } from './ui';

export default function PayrollSetupPage() {
  const allowed = useIsPayroll();
  const [grades, setGrades] = useState<PayGrade[] | null>(null);
  const [rows, setRows] = useState<PayRow[] | null>(null);
  const [edit, setEdit] = useState<PayRow | null>(null);
  const [newGrade, setNewGrade] = useState({ name: '', base_salary: '' });

  const load = useCallback(() => {
    hr.pay.grades().then(setGrades).catch(() => setGrades([]));
    hr.pay.profiles().then(setRows).catch(() => setRows([]));
  }, []);
  useEffect(() => { if (allowed) load(); }, [allowed, load]);
  if (!allowed) return <p className="p-6 text-sm text-slate-500">Pay setup is open to administrators and HR only.</p>;

  const addGrade = async () => {
    try { await hr.pay.createGrade(newGrade); setNewGrade({ name: '', base_salary: '' }); load(); toast.success('Pay grade added.'); } catch (e) { toast.error(errorText(e, 'Could not add the grade.')); }
  };
  const removeGrade = async (g: PayGrade) => {
    if (!window.confirm(`Delete "${g.name}"? ${g.people} people use it; they fall back to their own salary.`)) return;
    try { await hr.pay.removeGrade(g.id); load(); } catch (e) { toast.error(errorText(e, 'Could not delete.')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <PageHead title="Pay setup" hint="Pay grades, tax withholding and benefits per person. Generating monthly salaries (Salary > Generate) starts every payslip from these figures." />

      <div className={card}>
        <h2 className="font-bold text-sm mb-2">Pay grades</h2>
        {grades === null ? <Spinner /> : (
          <>
            {grades.length === 0 ? <p className="text-sm text-slate-500 mb-2">No grades yet. Without one, a person's payslip uses the monthly salary on their staff record.</p> : (
              <ul className="divide-y divide-slate-100 mb-3">
                {grades.map((g) => (
                  <li key={g.id} className="py-2 flex items-center gap-3 text-sm">
                    <span className="font-semibold mr-auto">{g.name}</span><span>{formatMoney(Number(g.base_salary))}</span>
                    <span className="text-xs text-slate-500">{g.people} {g.people === 1 ? 'person' : 'people'}</span>
                    <button aria-label={`Delete ${g.name}`} className="text-slate-400 hover:text-rose-600" onClick={() => removeGrade(g)}><Trash2 className="w-4 h-4" /></button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              <input aria-label="Grade name" className={`${input} max-w-[14rem]`} placeholder="Grade name, e.g. Teacher L2" value={newGrade.name} onChange={(e) => setNewGrade({ ...newGrade, name: e.target.value })} />
              <input aria-label="Monthly base salary" type="number" min={0} className={`${input} max-w-[12rem]`} placeholder="Monthly base salary" value={newGrade.base_salary} onChange={(e) => setNewGrade({ ...newGrade, base_salary: e.target.value })} />
              <button className={btn} disabled={!newGrade.name.trim() || !newGrade.base_salary} onClick={addGrade}><Plus className="inline w-3.5 h-3.5 mr-1" />Add grade</button>
            </div>
          </>
        )}
      </div>

      <div className={`${card} overflow-x-auto`}>
        <h2 className="font-bold text-sm mb-2">What each person's payslip starts from</h2>
        {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>No active staff.</Empty> : (
          <table className="w-full text-sm min-w-[44rem]">
            <thead><tr className="text-left text-xs text-slate-500 border-b border-slate-200"><th className="py-1.5">Name</th><th>Grade</th><th className="text-right">Basic</th><th className="text-right">Allowances</th><th className="text-right">Tax</th><th className="text-right">Deductions</th><th className="text-right">Net</th><th /></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.teacher_id} className="border-b border-slate-100">
                  <td className="py-1.5"><span className="font-semibold">{r.name}</span><span className="block text-xs text-slate-500">{r.role}</span></td>
                  <td>{r.pay_grade_name || <Pill tone="slate">{r.monthly_salary != null ? 'own salary' : 'no pay set'}</Pill>}</td>
                  <td className="text-right">{formatMoney(r.basic)}</td><td className="text-right">{formatMoney(r.allowances)}</td>
                  <td className="text-right">{formatMoney(r.tax)}{r.tax_rate_percent ? <span className="text-xs text-slate-500"> ({r.tax_rate_percent}%)</span> : null}</td>
                  <td className="text-right">{formatMoney(r.benefit_deductions)}</td><td className="text-right font-bold">{formatMoney(r.net)}</td>
                  <td className="text-right"><button className="text-xs font-bold text-emerald-700" onClick={() => setEdit(r)}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {edit && <ProfileModal row={edit} grades={grades || []} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
    </div>
  );
}

function ProfileModal({ row, grades, onClose, onSaved }: { row: PayRow; grades: PayGrade[]; onClose: () => void; onSaved: () => void }) {
  const [grade, setGrade] = useState(row.pay_grade || '');
  const [tax, setTax] = useState(String(row.tax_rate_percent || 0));
  const [benefits, setBenefits] = useState<Benefit[]>(row.benefits);
  const [saving, setSaving] = useState(false);
  const setB = (i: number, patch: Partial<Benefit>) => setBenefits((b) => b.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const save = async () => {
    setSaving(true);
    try { await hr.pay.saveProfile(row.teacher_id, { pay_grade: grade || null, tax_rate_percent: tax || 0, benefits }); toast.success('Pay setup saved.'); onSaved(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };
  return (
    <Modal open onClose={onClose} title={`Pay setup · ${row.name}`} description={row.monthly_salary != null ? `Monthly salary on their staff record: ${formatMoney(row.monthly_salary)} (used when no grade is chosen).` : undefined} size="lg">
      <div className="space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Pay grade"><select aria-label="Pay grade" className={input} value={grade} onChange={(e) => setGrade(e.target.value)}><option value="">No grade (use their own salary)</option>{grades.map((g) => <option key={g.id} value={g.id}>{g.name} · {formatMoney(Number(g.base_salary))}</option>)}</select></Field>
          <Field label="Tax withheld (% of basic + allowances)"><input aria-label="Tax rate" type="number" min={0} max={60} step="0.5" className={input} value={tax} onChange={(e) => setTax(e.target.value)} /></Field>
        </div>
        <div>
          <p className="text-xs font-bold text-slate-600 mb-1">Benefits and other deductions</p>
          <div className="space-y-2">
            {benefits.map((b, i) => (
              <div key={i} className="flex gap-2">
                <input aria-label="Benefit name" className={input} placeholder="Transport, health plan…" value={b.name} onChange={(e) => setB(i, { name: e.target.value })} />
                <input aria-label="Benefit amount" type="number" min={0} className={`${input} max-w-[8rem]`} value={b.amount} onChange={(e) => setB(i, { amount: e.target.value })} />
                <select aria-label="Benefit kind" className={`${input} max-w-[9rem]`} value={b.kind} onChange={(e) => setB(i, { kind: e.target.value as Benefit['kind'] })}><option value="allowance">Adds to pay</option><option value="deduction">Deducted</option></select>
                <button aria-label="Remove" className="text-slate-400 hover:text-rose-600" onClick={() => setBenefits((x) => x.filter((_, j) => j !== i))}><Trash2 className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
          <button className="text-xs font-bold text-emerald-700 mt-2" onClick={() => setBenefits((x) => [...x, { name: '', amount: '', kind: 'allowance' }])}>+ Add a benefit</button>
        </div>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save'}</button></div>
      </div>
    </Modal>
  );
}
