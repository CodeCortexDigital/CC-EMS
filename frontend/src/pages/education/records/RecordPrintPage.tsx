// The printable cumulative record (指導要録) for one student: Print or Save as PDF with the browser, so Japanese characters always print.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Printer } from 'lucide-react';
import records, { CumulativeRecord, errorText } from '@/services/records.service';
import security from '@/services/security.service';
import RecordPrint from './RecordPrint';

export default function RecordPrintPage() {
  const { id = '' } = useParams();
  const [record, setRecord] = useState<CumulativeRecord | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    records.get(id).then((r) => live && setRecord(r)).catch((e) => live && setError(errorText(e, 'Could not load the record.')));
    return () => { live = false; };
  }, [id]);

  return (
    <div className="p-4 sm:p-6 bg-slate-100 min-h-screen print:bg-white print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4 print:hidden">
        <Link to={`/education/records/${id}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-900">
          <ArrowLeft className="w-4 h-4" />Back to the record
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Choose “Save as PDF” in the print window to keep a file.</span>
          <button type="button" onClick={() => { security.logPrint('records', id); window.print(); }} disabled={!record}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--app-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            <Printer className="w-4 h-4" />Print / PDF
          </button>
        </div>
      </div>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!record && !error && <p className="text-sm text-slate-500">Loading…</p>}
      {record && <div className="record-print-root bg-white shadow print:shadow-none mx-auto max-w-[210mm] p-[10mm] print:p-0"><RecordPrint rec={record} /></div>}
    </div>
  );
}
