import { useCallback, useEffect, useState } from 'react';
import { FileSignature } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { btn, btnGhost, card, Empty, errorText, Field, fmtDate, input, PageHead, Pill, Spinner } from '@/components/common/kit';
import forms, { MyForm } from '@/services/forms.service';

/** A parent's forms, one per child. Signing is final, so the screen says so before it is submitted. */
export default function ParentFormsPage() {
  const [rows, setRows] = useState<MyForm[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => { forms.mine().then(setRows).catch(() => setRows([])); }, []);
  useEffect(load, [load]);

  const waiting = (rows || []).filter((r) => r.status === 'pending');
  const done = (rows || []).filter((r) => r.status !== 'pending');

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="Forms to sign" hint="Permission slips and consent forms from the school, one for each child." />
      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty>The school has not sent you any forms.</Empty> : (
        <>
          <section aria-label="Waiting for you">
            <h2 className="font-bold text-sm mb-2">Waiting for you {waiting.length > 0 && <Pill tone="amber">{waiting.length}</Pill>}</h2>
            {waiting.length === 0 ? <Empty>Everything is signed. Thank you.</Empty> : (
              <ul className="space-y-2">{waiting.map((f) => <Row key={f.id} f={f} action={<button className={btn} onClick={() => setOpen(f.id)}>Read and sign</button>} />)}</ul>
            )}
          </section>
          {done.length > 0 && (
            <section aria-label="Done">
              <h2 className="font-bold text-sm mb-2">Done</h2>
              <ul className="space-y-2">{done.map((f) => <Row key={f.id} f={f} action={<button className={btnGhost} onClick={() => setOpen(f.id)}>View</button>} />)}</ul>
            </section>
          )}
        </>
      )}
      {open && <SignDialog id={open} onClose={() => setOpen(null)} onDone={() => { setOpen(null); load(); }} />}
    </div>
  );
}

function Row({ f, action }: { f: MyForm; action: React.ReactNode }) {
  return (
    <li className={`${card} flex flex-wrap items-center gap-3`}>
      <FileSignature className="w-4 h-4 text-emerald-700" />
      <div className="mr-auto">
        <p className="font-semibold text-sm">{f.title}</p>
        <p className="text-xs text-slate-500">For {f.student_name}{f.class_name && ` (${f.class_name})`}{f.due_date && ` · please sign by ${fmtDate(f.due_date)}`}</p>
      </div>
      {f.status === 'signed' && <Pill tone="green">Signed {fmtDate(f.signed_at)}</Pill>}
      {f.status === 'declined' && <Pill tone="slate">Declined</Pill>}
      {action}
    </li>
  );
}

function SignDialog({ id, onClose, onDone }: { id: string; onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState<MyForm | null>(null);
  const [name, setName] = useState('');
  const [agree, setAgree] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string | boolean>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { forms.mineOne(id).then(setForm).catch(() => onClose()); }, [id, onClose]);
  if (!form) return <Modal open onClose={onClose} title="Form"><Spinner /></Modal>;

  const readOnly = form.status !== 'pending';
  const missing = (form.questions || []).some((q) => q.required && !readOnly && (answers[q.id] === undefined || answers[q.id] === ''));

  const submit = async (decision: 'signed' | 'declined') => {
    setSaving(true);
    try { await forms.sign(id, { signer_name: name, agree, decision, answers }); toast.success(decision === 'signed' ? 'Signed. Thank you.' : 'Your answer was sent.'); onDone(); }
    catch (e) { toast.error(errorText(e, 'Could not send your signature.')); } finally { setSaving(false); }
  };

  return (
    <Modal open onClose={onClose} title={`${form.title}: ${form.student_name}`} size="lg">
      <div className="space-y-4">
        <p className="text-sm whitespace-pre-wrap rounded-lg bg-slate-50 border border-slate-200 p-3">{form.body}</p>
        {(form.questions || []).map((q) => (
          <Field key={q.id} label={`${q.label}${q.required ? ' *' : ''}`}>
            {q.type === 'yes_no' ? (
              <div className="flex gap-4 text-sm">{['yes', 'no'].map((v) => <label key={v} className="flex items-center gap-1.5"><input type="radio" name={q.id} disabled={readOnly} checked={(readOnly ? form.answers?.[q.id] : answers[q.id]) === v} onChange={() => setAnswers({ ...answers, [q.id]: v })} />{v === 'yes' ? 'Yes' : 'No'}</label>)}</div>
            ) : q.type === 'choice' ? (
              <select aria-label={q.label} className={input} disabled={readOnly} value={String((readOnly ? form.answers?.[q.id] : answers[q.id]) ?? '')} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}>
                <option value="">Choose…</option>{q.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <input aria-label={q.label} className={input} disabled={readOnly} value={String((readOnly ? form.answers?.[q.id] : answers[q.id]) ?? '')} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
            )}
          </Field>
        ))}
        {readOnly ? <p className="text-sm text-slate-600">{form.status === 'signed' ? 'Signed' : 'Declined'} by <b>{form.signer_name}</b> on {fmtDate(form.signed_at)}. A signed form cannot be changed.</p> : (
          <>
            <Field label="Type your full name to sign"><input aria-label="Your full name" className={input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></Field>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-0.5" checked={agree} onChange={(e) => setAgree(e.target.checked)} /><span>I have read this form and agree. I understand that my signature cannot be changed afterwards.</span></label>
            <div className="flex flex-wrap justify-end gap-2">
              <button className={btnGhost} disabled={saving || !name.trim() || !agree} onClick={() => submit('declined')}>I do not agree</button>
              <button className={btn} disabled={saving || !name.trim() || !agree || missing} onClick={() => submit('signed')}>Sign</button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
