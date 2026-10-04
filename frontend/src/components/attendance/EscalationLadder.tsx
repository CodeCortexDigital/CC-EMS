// The absence ladder editor: what the school does as a student's unexcused absences add up.
import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { btn, btnGhost, input } from '@/components/common/kit';
import type { EscalationStep } from '@/services/attendanceRegister.service';

const MAX_STEPS = 6;

export default function EscalationLadder({ steps, isCustom, onSave, onReset }: {
  steps: EscalationStep[]; isCustom: boolean; onSave: (steps: EscalationStep[]) => void; onReset: () => void;
}) {
  const [draft, setDraft] = useState<EscalationStep[]>(steps);
  useEffect(() => setDraft(steps), [steps]);

  const patch = (i: number, p: Partial<EscalationStep>) => setDraft(draft.map((s, k) => (k === i ? { ...s, ...p } : s)));
  const counts = draft.map((s) => s.count);
  const duplicate = new Set(counts).size !== counts.length;
  const invalid = draft.some((s) => !(s.count >= 1 && s.count <= 365) || !(s.days >= 7 && s.days <= 365));
  const changed = JSON.stringify(draft) !== JSON.stringify(steps);

  return (
    <section aria-label="Absence ladder" className="space-y-3">
      <div>
        <h3 className="font-semibold text-sm">Absence ladder</h3>
        <p className="text-xs text-slate-500 max-w-3xl">
          As unexcused absences add up, the family is told at every step. Higher steps can also warn your staff and open an intervention for a counselor.
          Excused absences never count, and each step is sent once until its days have passed.
        </p>
      </div>

      {draft.length === 0 && <p className="text-sm text-amber-800">There are no steps, so families are not warned about repeated absences.</p>}
      <ul className="space-y-2">
        {draft.map((s, i) => (
          <li key={i} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <label className="flex items-center gap-1.5">At
              <input aria-label={`Step ${i + 1} absences`} type="number" min={1} max={365} className={`${input} w-16`} value={s.count} onChange={(e) => patch(i, { count: Number(e.target.value) })} />
              unexcused absences in
              <input aria-label={`Step ${i + 1} days`} type="number" min={7} max={365} className={`${input} w-16`} value={s.days} onChange={(e) => patch(i, { days: Number(e.target.value) })} />
              days
            </label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={s.staff} onChange={(e) => patch(i, { staff: e.target.checked })} aria-label={`Step ${i + 1} tell staff`} />Tell staff</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={s.intervention} onChange={(e) => patch(i, { intervention: e.target.checked })} aria-label={`Step ${i + 1} open an intervention`} />Open an intervention</label>
            <button aria-label={`Remove step ${i + 1}`} className="ml-auto text-slate-400 hover:text-rose-600" onClick={() => setDraft(draft.filter((_, k) => k !== i))}><Trash2 className="w-4 h-4" /></button>
          </li>
        ))}
      </ul>

      {duplicate && <p role="alert" className="text-xs text-rose-700">Two steps have the same number of absences. Give each step its own number.</p>}
      <div className="flex flex-wrap gap-2">
        <button className={btnGhost} disabled={draft.length >= MAX_STEPS} onClick={() => setDraft([...draft, { count: (draft.length ? draft[draft.length - 1].count : 0) + 2, days: 30, staff: true, intervention: false }])}><Plus className="inline w-3.5 h-3.5 mr-1" />Add a step</button>
        <button className={btn} disabled={!changed || duplicate || invalid} onClick={() => onSave([...draft].sort((a, b) => a.count - b.count))}>Save ladder</button>
        {isCustom && <button className={btnGhost} onClick={onReset}>Back to the usual steps (3, 5, 10)</button>}
      </div>
    </section>
  );
}
