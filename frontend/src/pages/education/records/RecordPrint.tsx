// The cumulative record (指導要録) laid out like MEXT's reference forms: 様式1 (学籍に関する記録) and 様式2 (指導に関する記録), for elementary,
// junior high and high school. Everything the form shows in a fixed place comes from `record.definition`, so this page and the editor
// can never disagree about what the form contains. Printed with the browser's Print / Save as PDF (so Japanese fonts always work).
import { Fragment, type ReactNode } from 'react';
import type { CumulativeRecord, RecordYear, SubjectDef } from '@/services/records.service';
import { LEVEL_LABEL } from '@/services/records.service';
import { wareki, warekiSchoolYear } from '@/utils/wareki';

const CSS = `
.rp{font-family:'Yu Mincho','Hiragino Mincho ProN','MS PMincho','Noto Serif JP',serif;color:#000;background:#fff}
.rp .page{width:190mm;min-height:270mm;margin:0 auto 8mm;padding:0;page-break-after:always;break-after:page;font-size:8.6pt;line-height:1.3}
.rp .page:last-child{page-break-after:auto;break-after:auto}
.rp table{border-collapse:collapse;width:100%;table-layout:fixed}
.rp td,.rp th{border:1px solid #000;padding:1.5px 3px;vertical-align:middle;word-break:break-all;font-weight:normal}
.rp .h{text-align:center;background:#fff;letter-spacing:.25em}
.rp .c{text-align:center}
.rp .tall td{height:11mm}
.rp .na{background:linear-gradient(to top right,transparent calc(50% - .5px),#000 calc(50% - .5px),#000 calc(50% + .5px),transparent calc(50% + .5px))}
.rp .title{text-align:center;font-size:15pt;letter-spacing:.4em;margin:2mm 0 1mm}
.rp .sub{font-size:7.5pt;margin-bottom:2mm}
.rp .outer{border:2px solid #000}
.rp .small{font-size:7pt}
.rp .seal{display:inline-block;border:1px solid #c00;color:#c00;border-radius:50%;width:6.5mm;height:6.5mm;line-height:6.2mm;text-align:center;font-size:7pt;margin-left:2px}
.rp .pre{white-space:pre-wrap}
.rp .tl{text-align:left;vertical-align:top}
@media print{
  body *{visibility:hidden}
  .record-print-root,.record-print-root *{visibility:visible}
  .record-print-root{position:absolute;left:0;top:0;width:100%}
  .rp .page{margin:0 auto;box-shadow:none}
  @page{size:A4 portrait;margin:10mm}
}
`;

const GENDER: Record<string, string> = { male: '男', female: '女' };
const yearOf = (rec: CumulativeRecord, grade: number): RecordYear | undefined => rec.years.find((y) => y.grade === grade);
/** 2026年度 is printed as 令和8年度, like the forms do. */
const yearLabel = (label?: string) => { const m = /^(\d{4})年度$/.exec(label || ''); return m ? warekiSchoolYear(`${m[1]}-04-01`) : (label || '年度'); };
const n = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v));

function Seal({ name, at }: { name: string; at: string | null }) {
  return <span>{name}{at ? <span className="seal" title={at.slice(0, 10)}>印</span> : null}</span>;
}

/** 区分/学年 header with a diagonal, as printed on the forms. */
function Corner({ a, b }: { a: string; b: string }) {
  return (
    <span style={{ position: 'relative', display: 'block', minHeight: '5.5mm' }}>
      <span style={{ position: 'absolute', right: 2, top: 0 }}>{b}</span>
      <span style={{ position: 'absolute', left: 2, bottom: 0 }}>{a}</span>
    </span>
  );
}

function PageHeaderGrid({ rec }: { rec: CumulativeRecord }) {
  const grades = Array.from({ length: rec.definition.grades }, (_, i) => i + 1);
  const person = rec.definition.person;
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '2mm' }}>
      <table style={{ width: `${Math.min(100, 20 + grades.length * 12)}%` }}>
        <tbody>
          <tr><td className="c" style={{ width: '24%' }}>区分 ╲ 学年</td>{grades.map((g) => <td key={g} className="c">{g}</td>)}</tr>
          <tr><td className="c">{rec.level === 'high' ? 'ホームルーム' : '学　級'}</td>{grades.map((g) => <td key={g} className="c">{yearOf(rec, g)?.class_name}</td>)}</tr>
          <tr><td className="c">整理番号</td>{grades.map((g) => <td key={g} className="c">{yearOf(rec, g)?.roll_number}</td>)}</tr>
        </tbody>
      </table>
      <span className="small" style={{ display: 'none' }}>{person}</span>
    </div>
  );
}

// ----------------------------------------------------------------------------------------------------- 様式1
function Register({ rec }: { rec: CumulativeRecord }) {
  const d = rec.definition;
  const high = rec.level === 'high';
  const junior = rec.level === 'junior_high';
  const person = d.person;
  const grades = Array.from({ length: d.grades }, (_, i) => i + 1);
  const blocks: number[][] = rec.level === 'elementary' ? [[1, 2, 3], [4, 5, 6]] : [grades];
  return (
    <section className="page">
      <h1 className="title">{high ? '高等学校（全日制の課程・定時制の課程）生徒指導要録' : d.label}（参考様式）</h1>
      <p className="sub">様式1（学籍に関する記録）</p>
      <PageHeaderGrid rec={rec} />
      <div className="outer">
        <table>
          <tbody>
            <tr><td className="h" colSpan={6} style={{ fontWeight: 'bold' }}>学　籍　の　記　録</td></tr>
            <tr>
              <td className="c" rowSpan={4} style={{ width: '5%' }}>{person.split('').join('\n')}</td>
              <td className="c" style={{ width: '9%' }}>ふりがな</td>
              <td style={{ width: '34%' }}>{rec.student_furigana}</td>
              <td className="c" style={{ width: '4%' }}>性別</td>
              <td className="c" rowSpan={2} style={{ width: '9%' }}>{high || junior ? '入学・編入学' : '入学・編入学等'}</td>
              <td rowSpan={2} className="c">
                {rec.entry_date ? <span>{wareki(rec.entry_date)}　{rec.entry_kind === 'admitted' ? `第${rec.entry_grade}学年編入学` : '第1学年入学'}</span> : <span>年　月　日　第1学年　入学<br />第　学年編入学</span>}
              </td>
            </tr>
            <tr className="tall"><td className="c">氏　名</td><td style={{ fontSize: '11pt' }}>{rec.student_name}</td><td className="c">{GENDER[rec.gender] || ''}</td></tr>
            <tr className="tall">
              <td className="c">生年月日</td><td colSpan={2} className="c">{rec.date_of_birth ? `${wareki(rec.date_of_birth)}生` : '年　月　日生'}</td>
              <td className="c">転入学</td>
              <td className="c">{rec.transfer_in_date ? `${wareki(rec.transfer_in_date)}　第${rec.transfer_in_grade ?? ''}学年転入学` : '年　月　日　第　学年転入学'}</td>
            </tr>
            <tr className="tall">
              <td className="c">現住所</td><td colSpan={2}>{rec.student_address}</td>
              <td className="c">{high ? '転学・退学' : '転学・退学等'}</td>
              <td>{rec.transfer_out_date ? `${wareki(rec.transfer_out_date)}　${rec.transfer_out_note}` : <span className="small">（　年　月　日）<br />　年　月　日</span>}</td>
            </tr>
            <tr>
              <td className="c" rowSpan={3}>保<br />護<br />者</td>
              <td className="c">ふりがな</td><td colSpan={2}>{rec.guardian_furigana}</td>
              <td className="c">{high ? '留学等' : '卒　業'}</td>
              <td className="c">{high
                ? (rec.abroad_from ? `${wareki(rec.abroad_from)} ～ ${wareki(rec.abroad_to)}` : '年　月　日　～　年　月　日')
                : (rec.graduation_date ? wareki(rec.graduation_date) : '年　月　日')}</td>
            </tr>
            <tr className="tall"><td className="c">氏　名</td><td colSpan={2}>{rec.guardian_name}</td>
              <td className="c">{high ? '卒　業' : junior ? '進学先\n就職先等' : '進学先'}</td>
              <td className={high ? 'c' : 'tl'} rowSpan={high ? 1 : 2}>{high ? (rec.graduation_date ? wareki(rec.graduation_date) : '年　月　日') : [rec.next_school, rec.next_work].filter(Boolean).join('　／　')}</td>
            </tr>
            <tr className="tall"><td className="c">現住所</td><td colSpan={2}>{rec.guardian_address}</td>
              {high && <><td className="c">進学先<br />就職先等</td><td>{[rec.next_school, rec.next_work].filter(Boolean).join('　／　')}</td></>}
            </tr>
            <tr style={{ height: '18mm' }}>
              <td className="c" colSpan={2}>入学前の経歴</td><td colSpan={high ? 2 : 4} className="tl pre">{rec.previous_history}</td>
              {high && <td colSpan={2} />}
            </tr>
          </tbody>
        </table>
        <table style={{ marginTop: 2 }}>
          <tbody>
            <tr style={{ height: '20mm' }}>
              <td className="c" style={{ width: '14%' }}>学 校 名<br />及　び<br />所 在 地<br /><span className="small">(分校名・所在地等)</span>{high ? <><br />課程名・学科名</> : null}</td>
              <td className="pre">{rec.school_name}{rec.school_address ? `\n${rec.school_address}` : ''}{high && rec.course_name ? `\n${rec.course_name}` : ''}</td>
            </tr>
          </tbody>
        </table>
        {blocks.map((block, bi) => (
          <table key={bi} style={{ marginTop: 2 }}>
            <tbody>
              <tr><td className="c" style={{ width: '14%' }}>年　度</td>{block.map((g) => <td key={g} className="c">{yearLabel(yearOf(rec, g)?.year_label)}</td>)}</tr>
              <tr><td><Corner a="区分" b="学年" /></td>{block.map((g) => <td key={g} className="c">{g}</td>)}</tr>
              <tr style={{ height: '16mm' }}><td className="c">校長氏名印</td>{block.map((g) => { const y = yearOf(rec, g); return <td key={g} className="c">{y ? <Seal name={y.principal_name} at={y.principal_confirmed_at} /> : null}</td>; })}</tr>
              <tr style={{ height: '16mm' }}><td className="c">{high ? 'ホームルーム\n担任者氏名印' : '学級担任者\n氏　名　印'}</td>{block.map((g) => { const y = yearOf(rec, g); return <td key={g} className="c">{y ? <Seal name={y.teacher_name} at={y.teacher_confirmed_at} /> : null}</td>; })}</tr>
            </tbody>
          </table>
        ))}
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------------------------------------- 様式2 pieces
function NameBar({ rec }: { rec: CumulativeRecord }) {
  const grades = Array.from({ length: rec.definition.grades }, (_, i) => i + 1);
  return (
    <table style={{ marginBottom: '2mm' }}>
      <tbody>
        <tr>
          <td className="c" style={{ width: '16%' }}>{rec.definition.person}氏名</td><td className="c" style={{ width: '16%' }} />
          <td className="c" style={{ width: '14%' }}>学校名</td><td className="c" />
          <td className="c" style={{ width: '9%' }}>区分 ╲ 学年</td>{grades.map((g) => <td key={g} className="c" style={{ width: '4.5%' }}>{g}</td>)}
        </tr>
        <tr>
          <td className="c" colSpan={2} rowSpan={2}>{rec.student_name}</td><td className="c" colSpan={2} rowSpan={2}>{rec.school_name}</td>
          <td className="c">{rec.level === 'high' ? 'ホームルーム' : '学　級'}</td>{grades.map((g) => <td key={g} className="c">{yearOf(rec, g)?.class_name}</td>)}
        </tr>
        <tr><td className="c">整理番号</td>{grades.map((g) => <td key={g} className="c">{yearOf(rec, g)?.roll_number}</td>)}</tr>
      </tbody>
    </table>
  );
}

function SubjectsTable({ rec, subjects }: { rec: CumulativeRecord; subjects: SubjectDef[] }) {
  const d = rec.definition;
  const grades = Array.from({ length: d.grades }, (_, i) => i + 1);
  return (
    <table>
      <colgroup><col style={{ width: '8%' }} /><col style={{ width: '40%' }} />{grades.map((g) => <col key={g} />)}</colgroup>
      <thead>
        <tr><td className="h" colSpan={2 + grades.length} style={{ fontWeight: 'bold' }}>各 教 科 の 学 習 の 記 録</td></tr>
        <tr><td className="c">教科</td><td><Corner a="観　点" b="学　年" /></td>{grades.map((g) => <td key={g} className="c">{g}</td>)}</tr>
      </thead>
      <tbody>
        {subjects.map((s) => (
          [...d.viewpoints.map((v) => ({ key: v.key as string, label: v.label })), { key: 'rating', label: '評定' }].map((row, i) => (
            <tr key={`${s.code}-${row.key}`}>
              {i === 0 && <td className="c" rowSpan={4} style={{ letterSpacing: '.2em' }}>{s.name.length > 3 ? s.name : s.name.split('').join('\n')}</td>}
              <td className="small" style={{ whiteSpace: 'nowrap', fontSize: '6.8pt' }}>{row.label}</td>
              {grades.map((g) => {
                const applicable = row.key === 'rating' ? s.rating_grades.includes(g) : s.grades.includes(g);
                if (!applicable) return <td key={g} className="na" />;
                const cell = yearOf(rec, g)?.content.subjects?.[s.code];
                const v = row.key === 'rating' ? cell?.rating : cell?.[row.key as 'v1' | 'v2' | 'v3'];
                return <td key={g} className="c">{v ?? ''}</td>;
              })}
            </tr>
          ))
        ))}
      </tbody>
    </table>
  );
}

function PerGradeText({ title, rec, grades, pick }: { title: string; rec: CumulativeRecord; grades: number[]; pick: (y: RecordYear) => string | undefined }) {
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '9%' }} /><col /></colgroup>
      <thead><tr><td className="h" colSpan={2} style={{ fontWeight: 'bold' }}>{title}</td></tr><tr><td className="c" style={{ width: '9%' }}>学年</td><td className="c">学習状況及び道徳性に係る成長の様子</td></tr></thead>
      <tbody>{grades.map((g) => <tr key={g} style={{ height: '10mm' }}><td className="c">{g}</td><td className="tl pre small">{pick(yearOf(rec, g) ?? ({} as RecordYear))}</td></tr>)}</tbody>
    </table>
  );
}

function Integrated({ rec, title }: { rec: CumulativeRecord; title: string }) {
  const grades = rec.definition.integrated_grades;
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '9%' }} /><col /><col /><col style={{ width: '40%' }} /></colgroup>
      <thead>
        <tr><td className="h" colSpan={4} style={{ fontWeight: 'bold' }}>{title}</td></tr>
        <tr><td className="c" style={{ width: '9%' }}>学年</td><td className="c">学 習 活 動</td><td className="c">観　点</td><td className="c" style={{ width: '40%' }}>評　価</td></tr>
      </thead>
      <tbody>{grades.map((g) => { const c = yearOf(rec, g)?.content; return (
        <tr key={g} style={{ height: '12.5mm' }}><td className="c">{g}</td><td className="tl pre small">{c?.integrated_activity}</td><td className="tl pre small">{c?.integrated_viewpoint}</td><td className="tl pre small">{c?.integrated_evaluation}</td></tr>
      ); })}</tbody>
    </table>
  );
}

function ForeignActivity({ rec }: { rec: CumulativeRecord }) {
  const grades = rec.definition.foreign_activity_grades;
  if (!grades.length) return null;
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '9%' }} /><col /><col /><col /></colgroup>
      <thead>
        <tr><td className="h" colSpan={4} style={{ fontWeight: 'bold' }}>外 国 語 活 動 の 記 録</td></tr>
        <tr><td className="c" style={{ width: '9%' }}>学年</td><td className="c">知識・技能</td><td className="c">思考・判断・表現</td><td className="c small">主体的に学習に取り組む態度</td></tr>
      </thead>
      <tbody>{grades.map((g) => { const c = yearOf(rec, g)?.content; return (
        <tr key={g} style={{ height: '9.5mm' }}><td className="c">{g}</td><td className="tl pre small">{c?.foreign_v1}</td><td className="tl pre small">{c?.foreign_v2}</td><td className="tl pre small">{c?.foreign_v3}</td></tr>
      ); })}</tbody>
    </table>
  );
}

function SpecialActivities({ rec }: { rec: CumulativeRecord }) {
  const d = rec.definition;
  const grades = Array.from({ length: d.grades }, (_, i) => i + 1);
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '28%' }} /><col style={{ width: '24%' }} />{grades.map((g) => <col key={g} />)}</colgroup>
      <thead>
        <tr><td className="h" colSpan={2 + grades.length} style={{ fontWeight: 'bold' }}>特 別 活 動 の 記 録</td></tr>
        <tr><td className="c" style={{ width: '28%' }}>内　容</td><td style={{ width: '24%' }}><Corner a="観　点" b="学　年" /></td>{grades.map((g) => <td key={g} className="c">{g}</td>)}</tr>
      </thead>
      <tbody>{d.special_activities.map((a, i) => (
        <tr key={a.key} style={{ height: '6.5mm' }}><td className="c">{a.label}</td>{i === 0 && <td rowSpan={d.special_activities.length} />}{grades.map((g) => <td key={g} className="c">{yearOf(rec, g)?.content.special_activities?.[a.key] ? '○' : ''}</td>)}</tr>
      ))}</tbody>
    </table>
  );
}

function Behaviour({ rec }: { rec: CumulativeRecord }) {
  const d = rec.definition;
  const grades = Array.from({ length: d.grades }, (_, i) => i + 1);
  const items = d.behaviour_items;
  const half = Math.ceil(items.length / 2);
  const left = items.slice(0, half), right = items.slice(half);
  const mark = (key: string, g: number) => (yearOf(rec, g)?.content.behaviour?.[key] ? '○' : '');
  return (
    <table>
      <colgroup>{[0, 1].map((k) => <Fragment key={k}><col style={{ width: '24%' }} />{grades.map((g) => <col key={g} style={{ width: `${26 / grades.length}%` }} />)}</Fragment>)}</colgroup>
      <thead>
        <tr><td className="h" colSpan={2 * (1 + grades.length)} style={{ fontWeight: 'bold' }}>行 動 の 記 録</td></tr>
        <tr>
          {[0, 1].map((k) => <Fragment key={k}><td><Corner a="項　目" b="学　年" /></td>{grades.map((g) => <td key={g} className="c">{g}</td>)}</Fragment>)}
        </tr>
      </thead>
      <tbody>{left.map((l, i) => (
        <tr key={l.key} style={{ height: '7mm' }}>
          <td>{l.label}</td>{grades.map((g) => <td key={g} className="c">{mark(l.key, g)}</td>)}
          <td>{right[i]?.label ?? ''}</td>{grades.map((g) => <td key={g} className="c">{right[i] ? mark(right[i].key, g) : ''}</td>)}
        </tr>
      ))}</tbody>
    </table>
  );
}

function Comments({ rec }: { rec: CumulativeRecord }) {
  const grades = Array.from({ length: rec.definition.grades }, (_, i) => i + 1);
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '8%' }} /><col /></colgroup>
      <thead><tr><td className="h" colSpan={2} style={{ fontWeight: 'bold' }}>総 合 所 見 及 び 指 導 上 参 考 と な る 諸 事 項</td></tr></thead>
      <tbody>{grades.map((g) => <tr key={g} style={{ height: rec.level === 'elementary' ? '22mm' : '30mm' }}><td className="c" style={{ width: '8%' }}>第{g}学年</td><td className="tl pre small">{yearOf(rec, g)?.content.comment}</td></tr>)}</tbody>
    </table>
  );
}

function Attendance({ rec }: { rec: CumulativeRecord }) {
  const grades = Array.from({ length: rec.definition.grades }, (_, i) => i + 1);
  const high = rec.level === 'high';
  return (
    <table style={{ marginTop: 3 }}>
      <colgroup><col style={{ width: '9%' }} />{Array.from({ length: high ? 6 : 5 }, (_, i) => <col key={i} />)}<col style={{ width: '28%' }} /></colgroup>
      <thead>
        <tr><td className="h" colSpan={high ? 8 : 7} style={{ fontWeight: 'bold' }}>出 欠 の 記 録</td></tr>
        <tr className="small">
          <td className="c"><Corner a="学年" b="区分" /></td><td className="c">授業日数</td><td className="c">出席停止・忌引等の日数</td>
          {high && <td className="c">留学中の授業日数</td>}<td className="c">出席しなければならない日数</td><td className="c">欠席日数</td><td className="c">出席日数</td><td className="c">備　考</td>
        </tr>
      </thead>
      <tbody>{grades.map((g) => { const y = yearOf(rec, g); return (
        <tr key={g} style={{ height: '7mm' }}>
          <td className="c">{g}</td><td className="c">{n(y?.school_days)}</td><td className="c">{n(y?.suspended_days)}</td>{high && <td className="c">{n(y?.abroad_days)}</td>}
          <td className="c">{n(y?.required_days)}</td><td className="c">{n(y?.absent_days)}</td><td className="c">{n(y?.present_days)}</td><td className="small">{y?.attendance_remarks}</td>
        </tr>
      ); })}</tbody>
    </table>
  );
}

// ----------------------------------------------------------------------------------------------------- high school
function HighCourses({ rec }: { rec: CumulativeRecord }) {
  const grades = [1, 2, 3, 4];
  type Row = { area: string; course: string };
  const rows: Row[] = [];
  rec.years.forEach((y) => (y.content.courses ?? []).forEach((c) => { if (!rows.some((r) => r.area === c.area && r.course === c.course)) rows.push({ area: c.area, course: c.course }); }));
  const cellOf = (r: Row, g: number) => yearOf(rec, g)?.content.courses?.find((c) => c.area === r.area && c.course === r.course);
  const totals = (rec.credit_totals as { courses?: Array<{ area: string; course: string; credits: number }>; total?: number }) || {};
  const sum = (r: Row) => totals.courses?.find((c) => c.area === r.area && c.course === r.course)?.credits ?? 0;
  return (
    <table>
      <thead>
        <tr><td className="h" colSpan={2 + grades.length * 3 + 1} style={{ fontWeight: 'bold' }}>各 教 科 ・ 科 目 等 の 学 習 の 記 録</td></tr>
        <tr className="small"><td className="c" rowSpan={2} style={{ width: '9%' }}>教科</td><td className="c" rowSpan={2} style={{ width: '17%' }}>科目</td>
          {grades.map((g) => <td key={g} className="c" colSpan={3}>第{g}学年</td>)}<td className="c" rowSpan={2} style={{ width: '6%' }}>修得単位数の計</td></tr>
        <tr className="small">{grades.map((g) => <Fragment key={g}><td className="c">学習状況</td><td className="c">評定</td><td className="c">単位</td></Fragment>)}</tr>
      </thead>
      <tbody>
        {rows.length === 0 && <tr><td colSpan={3 + grades.length * 3} className="c small" style={{ height: '12mm' }}>科目が登録されていません</td></tr>}
        {rows.map((r) => (
          <tr key={`${r.area}|${r.course}`} style={{ height: '6mm' }}>
            <td className="small">{r.area}</td><td className="small">{r.course}</td>
            {grades.map((g) => { const c = cellOf(r, g); return (
              <Fragment key={g}>
                <td className="c small">{c ? [c.v1, c.v2, c.v3].filter(Boolean).join('') : ''}</td>
                <td className="c">{c?.rating ?? ''}</td><td className="c">{c?.credits ?? ''}</td>
              </Fragment>
            ); })}
            <td className="c">{sum(r) || ''}</td>
          </tr>
        ))}
        <tr><td className="c" colSpan={2}>合　計</td><td colSpan={grades.length * 3} /><td className="c">{totals.total ?? 0}</td></tr>
      </tbody>
    </table>
  );
}

function PageTitle({ rec, text }: { rec: CumulativeRecord; text: string }) {
  return <p className="sub">{text}　<span className="small">{LEVEL_LABEL[rec.level]}　{rec.student_name}</span></p>;
}

function Guidance({ rec }: { rec: CumulativeRecord }) {
  const d = rec.definition;
  if (rec.level === 'high') {
    return (
      <>
        <section className="page">
          <PageTitle rec={rec} text="様式2（指導に関する記録）" />
          <NameBar rec={rec} />
          <div className="outer"><HighCourses rec={rec} /></div>
          <p className="small" style={{ marginTop: 2 }}>※「学習状況」欄には、左から「知識・技能」、「思考・判断・表現」、「主体的に学習に取り組む態度」の評価を記入</p>
        </section>
        <section className="page">
          <PageTitle rec={rec} text="様式2（指導に関する記録）　続き" />
          <div className="outer">
            <Integrated rec={rec} title="総 合 的 な 探 究 の 時 間 の 記 録" />
            <SpecialActivities rec={rec} />
            <Comments rec={rec} />
            <Attendance rec={rec} />
          </div>
        </section>
      </>
    );
  }
  const half = Math.ceil(d.subjects.length / 2);
  const leftSubjects = rec.level === 'junior_high' ? d.subjects.slice(0, half) : d.subjects;
  const rightSubjects = rec.level === 'junior_high' ? d.subjects.slice(half) : [];
  return (
    <>
      <section className="page">
        <PageTitle rec={rec} text="様式2（指導に関する記録）" />
        <NameBar rec={rec} />
        <div className="outer" style={{ display: 'flex', gap: 3 }}>
          <div style={{ flex: '0 0 56%' }}><SubjectsTable rec={rec} subjects={leftSubjects} /></div>
          <div style={{ flex: 1 }}>
            {rightSubjects.length > 0 && <div style={{ marginBottom: 3 }}><SubjectsTable rec={rec} subjects={rightSubjects} /></div>}
            <PerGradeText title="特 別 の 教 科　道 徳" rec={rec} grades={d.moral_grades} pick={(y) => y.content?.moral} />
            <ForeignActivity rec={rec} />
            <Integrated rec={rec} title="総 合 的 な 学 習 の 時 間 の 記 録" />
            <SpecialActivities rec={rec} />
          </div>
        </div>
      </section>
      <section className="page">
        <PageTitle rec={rec} text="様式2（指導に関する記録）　続き" />
        <div className="outer">
          <Behaviour rec={rec} />
          <Comments rec={rec} />
          <Attendance rec={rec} />
        </div>
      </section>
    </>
  );
}

function CreditBack({ rec }: { rec: CumulativeRecord }) {
  const totals = (rec.credit_totals as { courses?: Array<{ area: string; course: string; credits: number }>; total?: number }) || {};
  return (
    <section className="page">
      <p className="sub">（様式1裏面）　各教科・科目等の修得単位数の記録</p>
      <div className="outer">
        <table>
          <thead><tr><td className="c" style={{ width: '22%' }}>教科</td><td className="c">科目</td><td className="c" style={{ width: '18%' }}>修得単位数の計</td></tr></thead>
          <tbody>
            {(totals.courses ?? []).map((c) => <tr key={`${c.area}|${c.course}`}><td>{c.area}</td><td>{c.course}</td><td className="c">{c.credits}</td></tr>)}
            <tr><td className="c" colSpan={2}>合　計（総合的な探究の時間を含まない）</td><td className="c">{totals.total ?? 0}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** The whole record as printable pages. */
export default function RecordPrint({ rec }: { rec: CumulativeRecord }): ReactNode {
  return (
    <div className="rp" data-testid="record-print">
      <style>{CSS}</style>
      <Register rec={rec} />
      {rec.level === 'high' && <CreditBack rec={rec} />}
      <Guidance rec={rec} />
    </div>
  );
}
