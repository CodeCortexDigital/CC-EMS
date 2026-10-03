import { useCallback, useEffect, useState } from 'react';
import { BellRing, Download, FilePlus2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDate, fmtDateTime, input, PageHead, Pill, Spinner } from '@/components/common/kit';
import forms, { FormTemplate, Question, QuestionType, Tracker } from '@/services/forms.service';

const STATUS_TONE = { draft: 'slate', published: 'green', archived: 'amber' } as const;
const TYPE_LABEL: Record<QuestionType, string> = { yes_no: 'Yes / No', text: 'Short answer', choice: 'Choose one' };

export default function FormsPage() {
  const [rows, setRows] = useState<FormTemplate[] | null>(null);
  const [editing, setEditing] = useState<FormTemplate | 'new' | null>(null);
  const [tracking, setTracking] = useState<FormTemplate | null>(null);

  const load = useCallback(() => { forms.list().then(setRows).catch(() => setRows([])); }, []);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(errorText(e, 'That did not work.')); } };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Forms and permission slips" hint="Send a form to families, collect their signatures online, and see who has not signed.">
        <button className={btn} onClick={() => setEditing('new')}><FilePlus2 className="inline w-3.5 h-3.5 mr-1" />New form</button>
      </PageHead>

      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>No forms yet. Create one for a field trip or photo consent.</Empty> : (
        <ul className="space-y-2">
          {rows.map((t) => (
            <li key={t.id} className={card}>
              <div className="flex flex-wrap items-center gap-2">
                <b className="text-sm">{t.title}</b> <span className="text-xs text-slate-400">v{t.version}</span>
                <Pill tone={STATUS_TONE[t.status]}>{t.status}</Pill>
                {t.status !== 'draft' && <span className="text-xs text-slate-600">{t.counts.signed} signed · {t.counts.declined} declined · <b>{t.counts.pending} waiting</b> of {t.counts.total}</span>}
                {t.due_date && <span className="text-xs text-slate-400">due {fmtDate(t.due_date)}</span>}
                <span className="ml-auto flex flex-wrap gap-2">
                  {t.status === 'draft' && <><button className={btnGhost} onClick={() => setEditing(t)}>Edit</button><button className={btn} onClick={() => run(() => forms.publish(t.id), 'Published. Families have been notified.')}>Publish</button></>}
                  {t.status === 'published' && <><button className={btnGhost} onClick={() => setTracking(t)}>Who has signed</button><button className={btnGhost} onClick={() => run(() => forms.newVersion(t.id), 'New draft version created.')}>New version</button></>}
                  {t.status !== 'draft' && t.status !== 'published' && <button className={btnGhost} onClick={() => setTracking(t)}>Results</button>}
                  {t.status === 'published' && <button className={btnGhost} onClick={() => window.confirm('Archive this form? Families can no longer sign it.') && run(() => forms.archive(t.id), 'Archived.')}>Archive</button>}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && <FormEditor initial={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
      {tracking && <TrackerDialog template={tracking} onClose={() => { setTracking(null); load(); }} />}
    </div>
  );
}

const blankQuestion = (n: number): Question => ({ id: `q${n}`, label: '', type: 'yes_no', options: [], required: true });

function FormEditor({ initial, onClose, onSaved }: { initial: FormTemplate | null; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(initial?.title || '');
  const [body, setBody] = useState(initial?.body || '');
  const [due, setDue] = useState(initial?.due_date || '');
  const [audience, setAudience] = useState<'everyone' | 'classes'>(initial?.audience || 'everyone');
  const [classIds, setClassIds] = useState<string[]>(initial?.classes || []);
  const [questions, setQuestions] = useState<Question[]>(initial?.questions?.length ? initial.questions : []);
  const [classes, setClasses] = useState<Array<{ id: string; name: string }>>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => { forms.classes().then(setClasses).catch(() => setClasses([])); }, []);
  const patch = (i: number, p: Partial<Question>) => setQuestions(questions.map((q, k) => (k === i ? { ...q, ...p } : q)));

  const save = async () => {
    setSaving(true);
    const payload = { title, body, due_date: due || null, audience, classes: audience === 'classes' ? classIds : [], questions };
    try { initial ? await forms.update(initial.id, payload) : await forms.create(payload); toast.success('Saved as a draft.'); onSaved(); }
    catch (e) { toast.error(errorText(e, 'Could not save.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title={initial ? 'Edit form' : 'New form'} size="xl">
      <div className="space-y-3">
        <Field label="Title"><input aria-label="Form title" className={input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Zoo trip permission" /></Field>
        <Field label="What families are agreeing to"><textarea aria-label="Form text" className={input} rows={5} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Send to"><select aria-label="Audience" className={input} value={audience} onChange={(e) => setAudience(e.target.value as 'everyone' | 'classes')}><option value="everyone">Every family</option><option value="classes">Chosen classes</option></select></Field>
          <Field label="Sign by"><input aria-label="Due date" type="date" className={input} value={due} onChange={(e) => setDue(e.target.value)} /></Field>
        </div>
        {audience === 'classes' && (
          <fieldset><legend className="text-xs font-bold text-slate-600 mb-1">Classes</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {classes.map((c) => <label key={c.id} className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={classIds.includes(c.id)} onChange={() => setClassIds(classIds.includes(c.id) ? classIds.filter((x) => x !== c.id) : [...classIds, c.id])} />{c.name}</label>)}
            </div>
          </fieldset>
        )}

        <section aria-label="Questions">
          <div className="flex items-center mb-1"><h3 className="font-bold text-sm mr-auto">Questions</h3><button className={btnGhost} onClick={() => setQuestions([...questions, blankQuestion(questions.length + 1)])}>Add a question</button></div>
          {questions.length === 0 && <p className="text-xs text-slate-500">No questions: families will only read and sign.</p>}
          <ul className="space-y-2">
            {questions.map((q, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-2 grid gap-2 md:grid-cols-12">
                <input aria-label={`Question ${i + 1}`} className={`${input} md:col-span-5`} placeholder="Question" value={q.label} onChange={(e) => patch(i, { label: e.target.value })} />
                <select aria-label={`Question ${i + 1} type`} className={`${input} md:col-span-3`} value={q.type} onChange={(e) => patch(i, { type: e.target.value as QuestionType })}>{Object.entries(TYPE_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                <label className="md:col-span-2 flex items-center gap-1.5 text-xs"><input type="checkbox" checked={q.required} onChange={(e) => patch(i, { required: e.target.checked })} />Required</label>
                <button aria-label={`Remove question ${i + 1}`} className="md:col-span-1 text-slate-400 hover:text-rose-600" onClick={() => setQuestions(questions.filter((_, k) => k !== i))}><Trash2 className="w-4 h-4" /></button>
                {q.type === 'choice' && <input aria-label={`Question ${i + 1} options`} className={`${input} md:col-span-12`} placeholder="Options, separated by commas" value={q.options.join(', ')} onChange={(e) => patch(i, { options: e.target.value.split(',').map((o) => o.trim()).filter(Boolean) })} />}
              </li>
            ))}
          </ul>
        </section>
        <div className="flex justify-end gap-2"><button className={btnGhost} onClick={onClose}>Cancel</button><button className={btn} disabled={saving || !title.trim() || !body.trim()} onClick={save}>Save draft</button></div>
      </div>
    </Modal>
  );
}

function TrackerDialog({ template, onClose }: { template: FormTemplate; onClose: () => void }) {
  const [data, setData] = useState<Tracker | null>(null);
  const [filter, setFilter] = useState('');
  const load = useCallback(() => { forms.tracker(template.id, filter || undefined).then(setData).catch(() => setData(null)); }, [template.id, filter]);
  useEffect(load, [load]);

  const remind = async () => {
    try { const r = await forms.remind(template.id); toast.success(`Reminded ${r.reminded} famil${r.reminded === 1 ? 'y' : 'ies'}.`); load(); } catch (e) { toast.error(errorText(e, 'Could not send reminders.')); }
  };
  const download = async () => {
    try {
      const url = URL.createObjectURL(await forms.exportCsv(template.id));
      const a = document.createElement('a'); a.href = url; a.download = `${template.title}.csv`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { toast.error(errorText(e, 'Could not export.')); }
  };

  return (
    <Modal open onClose={onClose} title={template.title} size="xl">
      {!data ? <Spinner /> : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Pill tone="green">{data.counts.signed} signed</Pill><Pill tone="amber">{data.counts.pending} not signed</Pill><Pill tone="slate">{data.counts.declined} declined</Pill>
            <select aria-label="Show" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">Everyone</option><option value="pending">Not signed</option><option value="signed">Signed</option><option value="declined">Declined</option>
            </select>
            <span className="ml-auto flex gap-2">
              <button className={btnGhost} onClick={download}><Download className="inline w-3.5 h-3.5 mr-1" />Download CSV</button>
              {template.status === 'published' && <button className={btn} disabled={data.counts.pending === 0} onClick={remind}><BellRing className="inline w-3.5 h-3.5 mr-1" />Remind families who have not signed</button>}
            </span>
          </div>
          {data.rows.length === 0 ? <Empty>Nobody matches.</Empty> : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="py-1">Student</th><th>Class</th><th>Status</th><th>Signed by</th><th>When</th></tr></thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="py-1.5 font-semibold">{r.student_name}</td><td>{r.class_name}</td>
                    <td><Pill tone={r.status === 'signed' ? 'green' : r.status === 'declined' ? 'slate' : 'amber'}>{r.status === 'pending' ? 'not signed' : r.status}</Pill></td>
                    <td>{r.signer_name}</td><td className="text-xs text-slate-500">{fmtDateTime(r.signed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </Modal>
  );
}
