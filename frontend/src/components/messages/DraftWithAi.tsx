// "Draft with AI" for a message to a family. Fills the subject and message for the teacher to edit; never sends anything.
import { useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import StudentPicker from '@/components/common/StudentPicker';
import { btn, errorText, input } from '@/components/common/kit';
import teacherAi, { MESSAGE_KIND_LABEL, TONE_LABEL, type MessageKind, type Tone } from '@/services/teacherAi.service';
import type { StudentHit } from '@/services/frontdesk.service';

export default function DraftWithAi({ onDraft }: { onDraft: (d: { subject: string; body: string }) => void }) {
  const [open, setOpen] = useState(false);
  const [student, setStudent] = useState<StudentHit | null>(null);
  const [kind, setKind] = useState<MessageKind>('missed_assignments');
  const [tone, setTone] = useState<Tone>('warm');
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ source: string; warnings: string[] } | null>(null);

  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline"><Sparkles className="w-3.5 h-3.5" /> Draft with AI</button>;
  }

  const run = async () => {
    if (!student) return;
    setBusy(true);
    try {
      const d = await teacherAi.parentMessage({ student: student.id, template: kind, details, tone });
      onDraft({ subject: d.subject, body: d.body });
      setNote({ source: d.source, warnings: d.warnings });
    } catch (e) {
      toast.error(errorText(e, 'Could not draft the message.'));
    } finally { setBusy(false); }
  };

  return (
    <section aria-label="Draft with AI" className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 space-y-2">
      <p className="text-xs font-bold text-indigo-900 flex items-center gap-1"><Sparkles className="w-3.5 h-3.5" /> Draft with AI</p>
      <p className="text-[11px] text-slate-600">Only the student&apos;s first name and your notes are used. You read and edit the draft before it is sent.</p>
      {student
        ? <p className="text-sm">About <b>{student.name}</b> <button type="button" className="text-xs underline" onClick={() => setStudent(null)}>change</button></p>
        : <StudentPicker onPick={setStudent} label="Which student is this about?" />}
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs font-semibold">Type<select aria-label="Message type" className={input} value={kind} onChange={(e) => setKind(e.target.value as MessageKind)}>
          {(Object.keys(MESSAGE_KIND_LABEL) as MessageKind[]).map((k) => <option key={k} value={k}>{MESSAGE_KIND_LABEL[k]}</option>)}</select></label>
        <label className="text-xs font-semibold">Tone<select aria-label="Tone" className={input} value={tone} onChange={(e) => setTone(e.target.value as Tone)}>
          {(Object.keys(TONE_LABEL) as Tone[]).map((k) => <option key={k} value={k}>{TONE_LABEL[k]}</option>)}</select></label>
      </div>
      <label className="block text-xs font-semibold">What do you want to say?
        <textarea aria-label="Your notes" rows={3} className={input} placeholder="A few facts: what happened, when, what you would like to happen next" value={details} onChange={(e) => setDetails(e.target.value)} />
      </label>
      <div className="flex items-center gap-2">
        <button type="button" className={btn} disabled={busy || !student || !details.trim()} onClick={run}>{busy ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : 'Draft the message'}</button>
        <button type="button" className="text-xs underline" onClick={() => setOpen(false)}>Close</button>
      </div>
      {note && (
        <div className="text-xs space-y-1">
          <p className="text-slate-600">{note.source === 'ai' ? 'Drafted by AI. Read it and edit it before you send.' : 'Filled in from a standard template (AI is not set up). Edit it before you send.'}</p>
          {note.warnings.map((w) => <p key={w} role="alert" className="text-amber-800">{w}</p>)}
        </div>
      )}
    </section>
  );
}
