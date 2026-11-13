// The printable term report (通知表): Print or Save as PDF with the browser, so Japanese characters always print.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Printer } from 'lucide-react';
import security from '@/services/security.service';
import termReports, { errorText, TermReport } from '@/services/termReports.service';

const CSS = `
.tr{font-family:'Yu Mincho','Hiragino Mincho ProN','MS PMincho','Noto Serif JP',serif;color:#000;background:#fff;font-size:10pt;line-height:1.4}
.tr table{border-collapse:collapse;width:100%}
.tr td,.tr th{border:1px solid #000;padding:2px 5px;font-weight:normal;vertical-align:middle}
.tr th{text-align:center;letter-spacing:.1em}
.tr .c{text-align:center}
.tr .title{text-align:center;font-size:18pt;letter-spacing:.5em;margin:0 0 4mm}
.tr .pre{white-space:pre-wrap;min-height:18mm;vertical-align:top}
.tr h3{font-size:10pt;margin:4mm 0 1mm}
@media print{
  body *{visibility:hidden}
  .term-print-root,.term-print-root *{visibility:visible}
  .term-print-root{position:absolute;left:0;top:0;width:100%}
  @page{size:A4 portrait;margin:12mm}
}
`;
const VP: Array<['v1' | 'v2' | 'v3', string]> = [['v1', '知識・技能'], ['v2', '思考・判断・表現'], ['v3', '主体的に学習に取り組む態度']];
const n = (v: number | null) => (v === null || v === undefined ? '' : String(v));

export function TermReportPrint({ rep }: { rep: TermReport }) {
  const lay = rep.layout, c = rep.content;
  return (
    <div className="tr">
      <style>{CSS}</style>
      <p className="title">{lay.title}</p>
      <table><tbody><tr>
        <th>学校名</th><td>{rep.school_name}</td><th>年度・学期</th><td>{rep.year_label} {rep.term_label}</td>
        <th>学級</th><td>{rep.class_name}</td><th>氏名</th><td>{rep.student_name}</td>
      </tr></tbody></table>
      <h3>各教科の学習の記録</h3>
      <table>
        <thead><tr><th>教科</th>{lay.viewpoints && VP.map(([k, l]) => <th key={k}>{l}</th>)}<th>評価</th></tr></thead>
        <tbody>
          {lay.subjects.map((s) => (
            <tr key={s}><td>{s}</td>{lay.viewpoints && VP.map(([k]) => <td key={k} className="c">{c.subjects?.[s]?.[k] || ''}</td>)}<td className="c">{c.subjects?.[s]?.rating || ''}</td></tr>
          ))}
        </tbody>
      </table>
      {lay.sections.conduct && lay.conduct_items.length > 0 && (<>
        <h3>行動の記録</h3>
        <table><tbody>
          {lay.conduct_items.reduce<string[][]>((rows, item, i) => { if (i % 2 === 0) rows.push([item]); else rows[rows.length - 1].push(item); return rows; }, []).map((pair, i) => (
            <tr key={i}>{pair.map((item) => <Fragment2 key={item} label={item} on={!!c.conduct?.[item]} />)}{pair.length === 1 && <><td /><td /></>}</tr>
          ))}
        </tbody></table>
      </>)}
      {lay.sections.attendance && (<>
        <h3>出欠の記録</h3>
        <table><thead><tr><th>授業日数</th><th>出席停止・忌引等</th><th>欠席日数</th><th>備考</th></tr></thead>
          <tbody><tr><td className="c">{n(rep.school_days)}</td><td className="c">{n(rep.suspended_days)}</td><td className="c">{n(rep.absent_days)}</td><td>{rep.attendance_remarks}</td></tr></tbody></table>
      </>)}
      {lay.sections.comments && lay.comment_fields.map((f) => (<div key={f.key}><h3>{f.label}</h3><table><tbody><tr><td className="pre">{c.comments?.[f.key] || ''}</td></tr></tbody></table></div>))}
      <table style={{ marginTop: '6mm' }}><tbody><tr><th>校長</th><td>{rep.principal_name}</td><th>担任</th><td>{rep.teacher_name}</td><th>保護者印</th><td style={{ width: '25mm' }} /></tr></tbody></table>
    </div>
  );
}
function Fragment2({ label, on }: { label: string; on: boolean }) { return <><td>{label}</td><td className="c" style={{ width: '10mm' }}>{on ? '○' : ''}</td></>; }

export default function TermReportPrintPage() {
  const { id = '' } = useParams();
  const [rep, setRep] = useState<TermReport | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    termReports.get(id).then((r) => live && setRep(r)).catch((e) => live && setError(errorText(e, 'Could not load the report.')));
    return () => { live = false; };
  }, [id]);
  return (
    <div className="p-4 sm:p-6 bg-slate-100 min-h-screen print:bg-white print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4 print:hidden">
        <Link to={`/education/term-reports/${id}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-900"><ArrowLeft className="w-4 h-4" />Back to the report</Link>
        <button type="button" onClick={() => { security.logPrint('term-report', id); window.print(); }} disabled={!rep} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--app-accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Printer className="w-4 h-4" />Print / PDF</button>
      </div>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!rep && !error && <p className="text-sm text-slate-500">Loading…</p>}
      {rep && <div className="term-print-root bg-white shadow print:shadow-none mx-auto max-w-[210mm] p-[10mm] print:p-0"><TermReportPrint rep={rep} /></div>}
    </div>
  );
}
