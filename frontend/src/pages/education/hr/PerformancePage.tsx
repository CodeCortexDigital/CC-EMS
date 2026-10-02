import { useCallback, useEffect, useState } from 'react';
import { Plus, Target } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import hr, { errorText, Goal, Review } from '@/services/hr.service';
import { btn, btnGhost, card, Empty, Field, fmtDate, input, PageHead, Pill, Spinner, StaffSelect, todayStr, useIsHr, useStaff } from './ui';

const KINDS: Array<[string, string]> = [['annual', 'Annual review'], ['mid_year', 'Mid-year review'], ['probation', 'Probation review'], ['observation', 'Classroom observation']];
const kindLabel = (k: string) => KINDS.find(([v]) => v === k)?.[1] || k;
const stars = (n: number | null) => (n ? '★'.repeat(n) + '☆'.repeat(5 - n) : 'not rated');

export default function PerformancePage() {
  const isHr = useIsHr();
  const staff = useStaff();
  const [tab, setTab] = useState<'reviews' | 'goals'>('reviews');
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [form, setForm] = useState<null | 'review' | 'goal'>(null);
  const [open, setOpen] = useState<Review | null>(null);

  const load = useCallback(() => {
    hr.reviews.list().then(setReviews).catch(() => setReviews([]));
    hr.goals.list().then(setGoals).catch(() => setGoals([]));
  }, []);
  useEffect(load, [load]);

  const setProgress = async (g: Goal, progress: number) => {
    try { await hr.goals.update(g.id, { progress, status: progress >= 100 ? 'done' : 'open' }); load(); } catch (e) { toast.error(errorText(e, 'Could not update the goal.')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Performance" hint={isHr ? 'Annual and mid-year reviews, classroom observations and goals. A review stays private until you share it with the person.' : 'Reviews shared with you and your goals.'}>
        {isHr && <button className={btn} onClick={() => setForm(tab === 'reviews' ? 'review' : 'goal')}><Plus className="inline w-3.5 h-3.5 mr-1" />{tab === 'reviews' ? 'New review' : 'New goal'}</button>}
      </PageHead>
      <div className="flex gap-2">
        {([['reviews', 'Reviews & observations'], ['goals', 'Goals']] as const).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-full text-xs font-bold border ${tab === k ? 'bg-emerald-600 text-white border-emerald-600' : 'border-slate-300'}`}>{l}</button>
        ))}
      </div>

      {tab === 'reviews' ? (reviews === null ? <Spinner /> : reviews.length === 0 ? <Empty>{isHr ? 'No reviews yet.' : 'Nothing has been shared with you yet.'}</Empty> : (
        <div className="space-y-2">
          {reviews.map((r) => (
            <button key={r.id} onClick={() => setOpen(r)} className={`${card} w-full text-left flex flex-wrap items-center gap-3 hover:border-emerald-400`}>
              <div className="mr-auto"><p className="font-bold text-sm">{r.teacher_name} · {kindLabel(r.kind)}{r.period_label ? ` · ${r.period_label}` : ''}</p><p className="text-xs text-slate-500">{fmtDate(r.review_date)}{r.reviewer_name ? ` · by ${r.reviewer_name}` : ''}</p></div>
              <span className="text-amber-500 text-sm" aria-label={`Rating ${r.rating ?? 'none'}`}>{stars(r.rating)}</span>
              <Pill tone={r.status === 'draft' ? 'amber' : r.status === 'shared' ? 'blue' : 'green'}>{r.status === 'draft' ? 'Draft (private)' : r.status === 'shared' ? 'Shared' : 'Acknowledged'}</Pill>
            </button>
          ))}
        </div>
      )) : (goals === null ? <Spinner /> : goals.length === 0 ? <Empty>No goals set.</Empty> : (
        <div className="space-y-2">
          {goals.map((g) => (
            <div key={g.id} className={card}>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <Target className="w-4 h-4 text-emerald-700" /><p className="font-bold text-sm mr-auto">{g.title}</p>
                <span className="text-xs text-slate-500">{g.teacher_name}{g.due_date ? ` · due ${fmtDate(g.due_date)}` : ''}</span>
                <Pill tone={g.status === 'done' ? 'green' : g.status === 'dropped' ? 'slate' : 'blue'}>{g.status === 'done' ? 'Achieved' : g.status === 'dropped' ? 'Dropped' : 'In progress'}</Pill>
              </div>
              {g.description && <p className="text-xs text-slate-600 mb-2">{g.description}</p>}
              <div className="flex items-center gap-3">
                <input aria-label={`Progress on ${g.title}`} type="range" min={0} max={100} step={5} value={g.progress} disabled={g.status === 'dropped'} className="flex-1 accent-emerald-600"
                  onChange={(e) => setGoals((gs) => (gs || []).map((x) => (x.id === g.id ? { ...x, progress: Number(e.target.value) } : x)))} onMouseUp={(e) => setProgress(g, Number((e.target as HTMLInputElement).value))} onKeyUp={(e) => setProgress(g, Number((e.target as HTMLInputElement).value))} onTouchEnd={(e) => setProgress(g, Number((e.target as HTMLInputElement).value))} />
                <span className="text-sm font-bold w-10 text-right">{g.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      ))}

      {form === 'review' && <ReviewForm staff={staff} onClose={() => setForm(null)} onDone={() => { setForm(null); load(); }} />}
      {form === 'goal' && <GoalForm staff={staff} onClose={() => setForm(null)} onDone={() => { setForm(null); load(); }} />}
      {open && <ReviewModal review={open} isHr={isHr} onClose={() => setOpen(null)} onChanged={load} />}
    </div>
  );
}

function ReviewForm({ staff, onClose, onDone }: { staff: ReturnType<typeof useStaff>; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ teacher: '', kind: 'annual', period_label: '', review_date: todayStr(), rating: 0, strengths: '', improvements: '', observed_class: '' });
  const save = async () => {
    try { await hr.reviews.create({ ...f, rating: f.rating || null }); toast.success('Saved as a private draft.'); onDone(); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title="New review" size="lg">
      <div className="space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Staff member"><StaffSelect label="Staff member" staff={staff} value={f.teacher} onChange={(v) => setF({ ...f, teacher: v })} /></Field>
          <Field label="Type"><select aria-label="Review type" className={input} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="Period (for example 2026-27)"><input aria-label="Period" className={input} value={f.period_label} onChange={(e) => setF({ ...f, period_label: e.target.value })} /></Field>
          <Field label="Date"><input aria-label="Review date" type="date" className={input} value={f.review_date} onChange={(e) => setF({ ...f, review_date: e.target.value })} /></Field>
        </div>
        {f.kind === 'observation' && <Field label="Lesson observed"><input aria-label="Lesson observed" className={input} placeholder="Grade 5 maths, period 2" value={f.observed_class} onChange={(e) => setF({ ...f, observed_class: e.target.value })} /></Field>}
        <Field label="Rating (1 needs improvement, 5 outstanding)">
          <div className="flex gap-1">{[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" aria-label={`${n} star`} onClick={() => setF({ ...f, rating: f.rating === n ? 0 : n })} className={`text-2xl ${n <= f.rating ? 'text-amber-500' : 'text-slate-300'}`}>★</button>)}</div>
        </Field>
        <Field label="Strengths"><textarea aria-label="Strengths" rows={3} className={input} value={f.strengths} onChange={(e) => setF({ ...f, strengths: e.target.value })} /></Field>
        <Field label="Areas to improve"><textarea aria-label="Areas to improve" rows={3} className={input} value={f.improvements} onChange={(e) => setF({ ...f, improvements: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.teacher || !f.review_date} onClick={save}>Save draft</button></div>
      </div>
    </Modal>
  );
}

function GoalForm({ staff, onClose, onDone }: { staff: ReturnType<typeof useStaff>; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ teacher: '', title: '', description: '', due_date: '' });
  const save = async () => {
    try { await hr.goals.create({ ...f, due_date: f.due_date || null }); toast.success('Goal set.'); onDone(); } catch (e) { toast.error(errorText(e, 'Could not save.')); }
  };
  return (
    <Modal open onClose={onClose} title="New goal">
      <div className="space-y-3">
        <Field label="Staff member"><StaffSelect label="Staff member" staff={staff} value={f.teacher} onChange={(v) => setF({ ...f, teacher: v })} /></Field>
        <Field label="Goal"><input aria-label="Goal" className={input} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Details"><textarea aria-label="Details" rows={2} className={input} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <Field label="Due"><input aria-label="Due date" type="date" className={input} value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Close</button><button className={btn} disabled={!f.teacher || !f.title.trim()} onClick={save}>Set goal</button></div>
      </div>
    </Modal>
  );
}

function ReviewModal({ review, isHr, onClose, onChanged }: { review: Review; isHr: boolean; onClose: () => void; onChanged: () => void }) {
  const [r, setR] = useState(review);
  const [comment, setComment] = useState(review.employee_comment);
  const share = async () => { try { setR(await hr.reviews.update(r.id, { status: 'shared' })); toast.success(`Shared with ${r.teacher_name}.`); onChanged(); } catch (e) { toast.error(errorText(e, 'Could not share.')); } };
  const ack = async () => { try { setR(await hr.reviews.acknowledge(r.id, comment)); toast.success('Thank you. Your acknowledgement is recorded.'); onChanged(); } catch (e) { toast.error(errorText(e, 'Could not acknowledge.')); } };
  const del = async () => { if (!window.confirm('Delete this review?')) return; try { await hr.reviews.remove(r.id); onChanged(); onClose(); } catch (e) { toast.error(errorText(e, 'Could not delete.')); } };
  return (
    <Modal open onClose={onClose} title={`${kindLabel(r.kind)}${r.period_label ? ` · ${r.period_label}` : ''}`} description={`${r.teacher_name} · ${fmtDate(r.review_date)}${r.reviewer_name ? ` · by ${r.reviewer_name}` : ''}`} size="lg">
      <div className="space-y-3 text-sm">
        <p className="text-amber-500 text-lg">{stars(r.rating)}</p>
        {r.observed_class && <p><b>Lesson observed:</b> {r.observed_class}</p>}
        <div><p className="text-xs font-black text-slate-500 uppercase">Strengths</p><p className="whitespace-pre-wrap">{r.strengths || 'None recorded.'}</p></div>
        <div><p className="text-xs font-black text-slate-500 uppercase">Areas to improve</p><p className="whitespace-pre-wrap">{r.improvements || 'None recorded.'}</p></div>
        {r.status === 'acknowledged' ? (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3"><p className="font-bold text-emerald-800">Acknowledged {r.acknowledged_at ? fmtDate(r.acknowledged_at) : ''}</p>{r.employee_comment && <p className="mt-1 whitespace-pre-wrap">{r.employee_comment}</p>}</div>
        ) : !isHr && (
          <div className="space-y-2"><Field label="Your comment (optional)"><textarea aria-label="Your comment" rows={3} className={input} value={comment} onChange={(e) => setComment(e.target.value)} /></Field><button className={btn} onClick={ack}>I have read this review</button></div>
        )}
        {isHr && (
          <div className="flex gap-2 pt-1">
            {r.status === 'draft' && <button className={btn} onClick={share}>Share with {r.teacher_name.split(' ')[0]}</button>}
            <button className="text-xs font-bold text-rose-700 ml-auto" onClick={del}>Delete</button>
          </div>
        )}
      </div>
    </Modal>
  );
}
