// Planning for the office: a written read of the figures, next year's enrolment, score trends and staff signals.
import { useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { btn, card, errorText, input } from '@/components/common/kit';
import planning, { type Forecast, type Narrative, type NarrativeReport, type Staffing, type Trends } from '@/services/planning.service';

const REPORTS: Array<[NarrativeReport, string]> = [['overview', 'School overview'], ['attendance', 'Attendance'], ['finance', 'Fees'], ['enrolment', 'Enrolment']];

function Summary() {
  const [report, setReport] = useState<NarrativeReport>('overview');
  const [out, setOut] = useState<Narrative | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setOut(await planning.narrative(report)); } catch (e) { toast.error(errorText(e, 'Could not write the summary.')); } finally { setBusy(false); }
  };
  return (
    <section className={card} aria-label="Written summary">
      <h2 className="font-bold">A short written read of the figures</h2>
      <p className="text-xs text-slate-500 mb-2">For the last 30 days. It only describes the numbers; it does not explain causes or predict.</p>
      <div className="flex flex-wrap gap-2 items-center">
        <select aria-label="Report" className={`${input} w-auto`} value={report} onChange={(e) => { setReport(e.target.value as NarrativeReport); setOut(null); }}>
          {REPORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button className={btn} onClick={run} disabled={busy}>{busy ? <Loader2 className="inline w-3.5 h-3.5 animate-spin" /> : <Sparkles className="inline w-3.5 h-3.5 mr-1" />}Write the summary</button>
      </div>
      {out && (
        <div className="mt-3 space-y-2">
          <p className="text-sm whitespace-pre-wrap">{out.summary}</p>
          <p className="text-[11px] text-slate-500">{out.source === 'ai' ? 'Written by AI from the figures below. Check it against them.' : 'The figures in plain words (AI is not set up).'}</p>
          <ul className="text-xs grid sm:grid-cols-2 gap-x-6 gap-y-0.5">
            {out.facts.map((f) => <li key={f.label}><b>{f.label}:</b> {String(f.value)}{f.change ? <span className="text-slate-500"> ({f.change})</span> : null}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

function ForecastSection() {
  const [d, setD] = useState<Forecast | null>(null);
  useEffect(() => { planning.forecast().then(setD).catch((e) => toast.error(errorText(e, 'Could not build the forecast.'))); }, []);
  if (!d) return <section className={card}><Loader2 className="w-4 h-4 animate-spin" /></section>;
  const a = d.assumptions;
  return (
    <section className={card} aria-label="Enrolment forecast">
      <h2 className="font-bold">Next year&apos;s enrolment{d.year ? ` (${d.year})` : ''}</h2>
      <p className="text-xs text-slate-500 mb-2">{a.how}</p>
      <p className="text-xs mb-2">
        Retention used: <b>{Math.round(a.retention * 100)}%</b>{a.retention_assumed ? ' (assumed: not enough history yet)' : ' (from the last 12 months)'}
        {' · '}Application conversion used: <b>{Math.round(a.conversion * 100)}%</b>{a.conversion_assumed ? ' (assumed: not enough decided applications yet)' : ''}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm tabular-nums">
          <thead><tr className="text-left text-[11px] uppercase text-slate-400"><th className="py-1 pr-3">Grade</th><th className="pr-3">This year</th><th className="pr-3">Expected</th><th className="pr-3">Range</th><th className="pr-3">Offers</th><th className="pr-3">Waiting</th><th className="pr-3">Seats left</th><th>Sections</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {d.grades.map((g) => (
              <tr key={g.grade}>
                <td className="py-1 pr-3 font-semibold">{g.label}</td><td className="pr-3">{g.this_year}</td><td className="pr-3 font-bold">{g.expected}</td>
                <td className="pr-3">{g.low}–{g.high}</td><td className="pr-3">{g.confirmed}</td><td className="pr-3">{g.pipeline}</td>
                <td className={`pr-3 ${g.seats_left != null && g.seats_left < 0 ? 'text-rose-700 font-bold' : ''}`}>{g.seats_left == null ? 'no limit set' : g.seats_left}</td>
                <td>{g.sections_needed}</td>
              </tr>
            ))}
            <tr className="font-bold"><td className="py-1 pr-3">All grades</td><td className="pr-3">{d.total.this_year}</td><td className="pr-3">{d.total.expected}</td><td className="pr-3">{d.total.low}–{d.total.high}</td><td colSpan={4} /></tr>
          </tbody>
        </table>
      </div>
      {d.grades.length === 0 && <p className="text-sm text-slate-500 py-2">No students or applications to forecast from yet.</p>}
      {d.unmatched_applications > 0 && <p className="text-xs text-amber-800 mt-2">{d.unmatched_applications} application(s) name a grade the forecast cannot read, so they are not counted.</p>}
    </section>
  );
}

function TrendsSection() {
  const [by, setBy] = useState<'subject' | 'class'>('subject');
  const [d, setD] = useState<Trends | null>(null);
  useEffect(() => { setD(null); planning.trends(by).then(setD).catch((e) => toast.error(errorText(e, 'Could not load the trends.'))); }, [by]);
  return (
    <section className={card} aria-label="Score trends">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-bold">Scores term over term</h2>
        <select aria-label="Group by" className={`${input} w-auto`} value={by} onChange={(e) => setBy(e.target.value as 'subject' | 'class')}><option value="subject">By subject</option><option value="class">By class</option></select>
      </div>
      {!d ? <Loader2 className="w-4 h-4 animate-spin mt-2" /> : (
        <>
          <p className="text-xs text-slate-500 mb-2">{d.note}</p>
          {d.groups.length === 0 ? <p className="text-sm text-slate-500 py-2">Not enough scores in two terms to compare yet.</p> : (
            <ul className="divide-y divide-slate-100 text-sm">
              {d.groups.map((g) => (
                <li key={g.name} className="py-1.5 flex flex-wrap items-center gap-x-4">
                  <span className="font-semibold w-40">{g.name}</span>
                  <span className="text-slate-600">{g.series.map((s) => `${s.term_name} ${s.average}%`).join(' → ')}</span>
                  <span className={`ml-auto font-bold ${g.declining ? 'text-rose-700' : g.change > 0 ? 'text-emerald-700' : 'text-slate-600'}`}>{g.change > 0 ? '+' : ''}{g.change} pts{g.declining ? ' · declining' : ''}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function StaffingSection() {
  const [d, setD] = useState<Staffing | null | 'denied'>(null);
  useEffect(() => { planning.staffing().then(setD).catch(() => setD('denied')); }, []);
  if (d === 'denied') return null;
  if (!d) return <section className={card}><Loader2 className="w-4 h-4 animate-spin" /></section>;
  return (
    <section className={card} aria-label="Staff signals">
      <h2 className="font-bold">Staff signals</h2>
      <p className="text-xs text-slate-500 mb-2">{d.note}</p>
      {d.staff.length === 0 ? <p className="text-sm text-slate-500 py-2">Nothing to flag among {d.active_staff} staff.</p> : (
        <ul className="divide-y divide-slate-100 text-sm">
          {d.staff.map((s) => (
            <li key={s.teacher_id} className="py-1.5">
              <b>{s.teacher_name}</b>
              <ul className="text-xs text-slate-600 ml-3 list-disc">{s.signals.map((x, i) => <li key={i}><b>{x.label}:</b> {x.detail}</li>)}</ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function PlanningPage() {
  return (
    <div className="space-y-4">
      <Summary />
      <ForecastSection />
      <TrendsSection />
      <StaffingSection />
    </div>
  );
}
