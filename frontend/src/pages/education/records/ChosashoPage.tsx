// The 調査書 of a junior-high student: a preview from the 指導要録, issue to a named high school, and the copies already issued.
// Printed with the browser's Print / Save as PDF, so Japanese characters always print.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';
import security from '@/services/security.service';
import chosasho, { Chosasho, ChosashoIssue } from '@/services/chosasho.service';
import { wareki } from '@/utils/wareki';
import { btn, btnGhost, card, input, PageHead, Pill, Spinner } from '../hr/ui';

const errorText = (e: any, fallback: string) => e?.response?.data?.issued_to || e?.response?.data?.detail || fallback;
const CSS = `
.cs{font-family:'Yu Mincho','Hiragino Mincho ProN','MS PMincho','Noto Serif JP',serif;color:#000;background:#fff;font-size:9.5pt;line-height:1.4}
.cs table{border-collapse:collapse;width:100%;margin-bottom:3mm}
.cs td,.cs th{border:1px solid #000;padding:2px 5px;font-weight:normal;vertical-align:middle}
.cs th{text-align:center;letter-spacing:.1em}
.cs .c{text-align:center}
.cs .title{text-align:center;font-size:18pt;letter-spacing:.6em;margin:0 0 3mm}
.cs .pre{white-space:pre-wrap;min-height:10mm;vertical-align:top}
.cs h3{font-size:10pt;margin:3mm 0 1mm}
@media print{
  body *{visibility:hidden}
  .cs-root,.cs-root *{visibility:visible}
  .cs-root{position:absolute;left:0;top:0;width:100%}
  @page{size:A4 portrait;margin:12mm}
}
`;
const GRADES = ['1', '2', '3'] as const;
const n = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v));

export function ChosashoPrint({ data, issuedTo }: { data: Chosasho; issuedTo?: string }) {
  const s = data.student;
  return (
    <div className="cs">
      <style>{CSS}</style>
      <p className="title">調査書</p>
      {issuedTo && <p style={{ textAlign: 'right' }}>{issuedTo} 御中</p>}
      <table><tbody>
        <tr><th>ふりがな</th><td>{s.furigana}</td><th>生年月日</th><td>{wareki(s.date_of_birth)}</td></tr>
        <tr><th>氏名</th><td>{s.name}</td><th>性別</th><td className="c">{s.gender === 'male' ? '男' : s.gender === 'female' ? '女' : ''}</td></tr>
        <tr><th>中学校名</th><td>{data.school.name}</td><th>卒業(見込)</th><td>{wareki(data.graduation.date)}</td></tr>
      </tbody></table>
      <h3>各教科の評定</h3>
      <table>
        <thead><tr><th>教科</th>{GRADES.map((g) => <th key={g}>第{g}学年</th>)}</tr></thead>
        <tbody>
          {data.subjects.map((sub) => <tr key={sub.code}><td>{sub.name}</td>{GRADES.map((g) => <td key={g} className="c">{n(sub.ratings[g])}</td>)}</tr>)}
          <tr><th>評定の合計</th>{GRADES.map((g) => <td key={g} className="c">{data.totals[g].count ? `${data.totals[g].sum} / ${data.totals[g].max}` : ''}</td>)}</tr>
        </tbody>
      </table>
      <h3>特別活動の記録</h3>
      <table><thead><tr><th>項目</th>{GRADES.map((g) => <th key={g}>第{g}学年</th>)}</tr></thead>
        <tbody>{data.special_activities.map((m) => <tr key={m.key}><td>{m.label}</td>{GRADES.map((g) => <td key={g} className="c">{m.years[g] ? '○' : ''}</td>)}</tr>)}</tbody></table>
      <h3>行動の記録</h3>
      <table><thead><tr><th>項目</th>{GRADES.map((g) => <th key={g}>第{g}学年</th>)}</tr></thead>
        <tbody>{data.behaviour.map((m) => <tr key={m.key}><td>{m.label}</td>{GRADES.map((g) => <td key={g} className="c">{m.years[g] ? '○' : ''}</td>)}</tr>)}</tbody></table>
      <h3>総合所見</h3>
      <table><tbody>{GRADES.map((g) => <tr key={g}><th style={{ width: '20mm' }}>第{g}学年</th><td className="pre">{data.comments[g]}</td></tr>)}</tbody></table>
      <h3>出欠の記録</h3>
      <table><thead><tr><th>学年</th><th>授業日数</th><th>出席停止・忌引等</th><th>欠席日数</th><th>備考</th></tr></thead>
        <tbody>{GRADES.map((g) => { const a = data.attendance[g]; return <tr key={g}><td className="c">第{g}学年</td><td className="c">{n(a?.school_days)}</td><td className="c">{n(a?.suspended_days)}</td><td className="c">{n(a?.absent_days)}</td><td>{a?.remarks || ''}</td></tr>; })}</tbody></table>
      <p>上記のとおり相違ないことを証明します。</p>
      <table><tbody><tr><th>作成日</th><td>{wareki(data.prepared_on)}</td><th>校長</th><td>{data.school.principal}</td></tr></tbody></table>
    </div>
  );
}

export default function ChosashoPage() {
  const { id = '' } = useParams();
  const { role } = useAuth();
  const isAdmin = String(role || '').toLowerCase() === 'admin';
  const [data, setData] = useState<Chosasho | null>(null);
  const [issues, setIssues] = useState<ChosashoIssue[]>([]);
  const [viewing, setViewing] = useState<ChosashoIssue | null>(null);
  const [to, setTo] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = () => chosasho.get(id).then((d) => { setData(d.chosasho); setIssues(d.issues); }).catch((e) => setError(errorText(e, 'Could not load the 調査書.')));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const issue = async () => {
    setBusy(true);
    try { const r = await chosasho.issue(id, to, note); toast.success('The 調査書 was issued and a copy was kept.'); setTo(''); setNote(''); setViewing(r); await load(); }
    catch (e) { toast.error(errorText(e, 'Could not issue it.')); } finally { setBusy(false); }
  };
  const view = async (i: ChosashoIssue) => { try { setViewing(await chosasho.issued(id, i.id)); } catch (e) { toast.error(errorText(e, 'Could not open it.')); } };

  if (error) return <div className="p-6"><p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p></div>;
  if (!data) return <div className="p-6"><Spinner /></div>;
  const shown = viewing?.snapshot || data;

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <PageHead title="調査書 (Report for high school admission)" hint="Made from the student's cumulative record. It can be issued once all three years have the principal's seal.">
        <Link to={`/education/records/${id}`} className={btnGhost}>Back to the record</Link>
        <button className={btn} onClick={() => { security.logPrint('chosasho', id); window.print(); }}>Print / PDF</button>
      </PageHead>

      {viewing && <div className={`${card} flex flex-wrap items-center gap-3`}><Pill tone="green">Issued copy</Pill><span className="text-sm">{viewing.issued_to} · {viewing.issued_at.slice(0, 10)} · {viewing.issued_by}</span>
        <button className={btnGhost} onClick={() => setViewing(null)}>Show the current preview</button></div>}
      {!viewing && !data.ready && (
        <div role="alert" className={`${card} border-amber-300`}>
          <p className="text-sm font-semibold text-amber-900">It cannot be issued yet:</p>
          <ul className="list-disc pl-5 text-sm text-amber-900">{data.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      {!viewing && isAdmin && (
        <div className={`${card} grid gap-3 sm:grid-cols-3`}>
          <label className="block text-xs font-bold text-slate-600">Issue to (提出先)
            <input className={`${input} mt-1 font-normal`} value={to} onChange={(e) => setTo(e.target.value)} placeholder="High school name" /></label>
          <label className="block text-xs font-bold text-slate-600">Note
            <input className={`${input} mt-1 font-normal`} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="flex items-end"><button className={btn} disabled={busy || !data.ready || !to.trim()} onClick={issue}>Issue it</button></div>
        </div>
      )}
      {issues.length > 0 && (
        <div className={card}>
          <h2 className="font-bold text-sm mb-1">Issued so far</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {issues.map((i) => <li key={i.id} className="py-1.5 flex flex-wrap items-center justify-between gap-2">
              <span>{i.issued_to} · {i.issued_at.slice(0, 10)} · {i.issued_by}{i.note ? ` · ${i.note}` : ''}</span>
              <button className="text-xs font-semibold text-blue-600" onClick={() => view(i)}>View this copy</button></li>)}
          </ul>
        </div>
      )}
      <div className="cs-root bg-white shadow print:shadow-none mx-auto max-w-[210mm] p-[10mm] print:p-0"><ChosashoPrint data={shown} issuedTo={viewing?.issued_to} /></div>
    </div>
  );
}
