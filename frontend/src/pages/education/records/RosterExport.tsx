import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import standards, { errorText, RosterPreview } from '@/services/standards.service';
import { btn, card, Spinner } from '../hr/ui';

/** MEXT standards → roster export: a OneRoster 1.1 zip for a learning portal or another system that reads it. */
export default function RosterExport() {
  const [contacts, setContacts] = useState(false);
  const [preview, setPreview] = useState<RosterPreview | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPreview(null);
    standards.rosterPreview(contacts).then(setPreview).catch((e) => toast.error(errorText(e, 'Could not load the roster preview.')));
  }, [contacts]);

  const download = async () => {
    setBusy(true);
    try { await standards.downloadRoster(contacts); } catch (e) { toast.error(errorText(e, 'Could not download the roster.')); } finally { setBusy(false); }
  };

  return (
    <section className={`${card} space-y-3`} aria-label="Roster export">
      <div>
        <h2 className="font-bold text-sm">Roster export (OneRoster)</h2>
        <p className="text-xs text-slate-600 mt-1">A OneRoster 1.1 file for a learning portal or another system that reads it: the school, years and terms, subjects, classes, students, teachers and who is in which class. Each download is recorded in the activity log.</p>
      </div>
      {preview === null ? <Spinner /> : (
        <>
          <p className="text-sm text-slate-700">
            {preview.files.users} people, {preview.files.classes} classes, {preview.files.courses} subjects, {preview.files.enrollments} enrolments.
            {preview.skipped.students_without_class > 0 && ` ${preview.skipped.students_without_class} students have no class yet, so they are listed but not enrolled.`}
          </p>
          <p className="text-xs text-slate-500">Left out: {preview.left_out.join('; ')}.</p>
        </>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={contacts} onChange={(e) => setContacts(e.target.checked)} />
        Include email addresses and phone numbers (only if the other system needs them)
      </label>
      <button className={btn} disabled={busy || preview === null} onClick={download}>Download the roster (zip)</button>
    </section>
  );
}
