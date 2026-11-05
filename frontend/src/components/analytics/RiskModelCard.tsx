// What the risk scores are, how they were made, what they are not, and who gets flagged. Written to be read by someone checking the claim.
import { useState } from 'react';
import { Info, Loader2 } from 'lucide-react';
import api from '@/services/api';

interface Group { group: string; students: number; flagged: number; flag_rate: number }
interface Fairness { groups: Group[]; lowest_to_highest_rate: number | null; hidden_small_groups: number }
interface Card {
  title: string; summary: string; training_data: string; levels: string; missing_data: string; human_review: string;
  models: { name: string; algorithm: string; inputs: string[]; rule: string }[];
  not_used: string[]; limits: string[]; available: boolean;
  latest_run: null | {
    id: string; ran_at: string; ran_by: string; students_scored: number;
    details: { training?: { real_rows?: number; synthetic_rows?: number; model_version?: string }; libraries?: Record<string, string>; level_counts?: Record<string, number>; data_gaps?: Record<string, number> };
    fairness: { gender?: Fairness; class?: Fairness };
  };
}

function Rates({ title, f }: { title: string; f?: Fairness }) {
  if (!f || f.groups.length === 0) return <p className="text-xs text-slate-500">{title}: no group is large enough (10 students) to show.</p>;
  return (
    <div className="text-xs">
      <p className="font-semibold text-slate-700">{title}{f.lowest_to_highest_rate != null && <span className="font-normal text-slate-500"> · lowest rate is {f.lowest_to_highest_rate} of the highest</span>}</p>
      <ul className="mt-0.5 space-y-0.5">{f.groups.map((g) => <li key={g.group}>{g.group}: {g.flagged} of {g.students} flagged high or critical ({g.flag_rate}%)</li>)}</ul>
    </div>
  );
}

export default function RiskModelCard() {
  const [card, setCard] = useState<Card | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');

  const toggle = async () => {
    setOpen((o) => !o);
    if (!card && !error) {
      try { setCard((await api.get('/ai/risk-model-card/')).data); } catch (e: any) { setError(e?.response?.data?.error || 'Could not load the explanation.'); }
    }
  };

  const run = card?.latest_run;
  return (
    <div className="mt-3">
      <button type="button" onClick={toggle} aria-expanded={open} className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-700 hover:underline">
        <Info size={13} /> How these scores are made, and what they are not
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700 space-y-3" data-testid="risk-model-card">
          {error ? <p className="text-red-700">{error}</p> : !card ? <Loader2 className="animate-spin text-slate-400" /> : (
            <>
              <p className="font-semibold text-slate-900">{card.summary}</p>
              <div>
                <p className="font-bold">The models</p>
                <ul className="mt-1 space-y-1.5">
                  {card.models.map((m) => (
                    <li key={m.name}><b>{m.name}</b> ({m.algorithm}). Inputs: {m.inputs.join(', ')}. {m.rule}</li>
                  ))}
                </ul>
              </div>
              <p><b>Training data.</b> {card.training_data}</p>
              <p><b>Levels.</b> {card.levels}</p>
              <p><b>Missing data.</b> {card.missing_data}</p>
              <p><b>Not used as inputs:</b> {card.not_used.join(', ')}.</p>
              <div><p className="font-bold">Limits</p><ul className="mt-1 list-disc pl-5 space-y-0.5">{card.limits.map((l) => <li key={l}>{l}</li>)}</ul></div>
              <p><b>Human review.</b> {card.human_review}</p>
              <div className="border-t border-slate-200 pt-3 space-y-2">
                <p className="font-bold">Your school&apos;s latest scan</p>
                {!run ? <p className="text-slate-500">No scan has been run yet.</p> : (
                  <>
                    <p>Run {new Date(run.ran_at).toLocaleString()} by {run.ran_by}. {run.students_scored} students scored
                      {run.details.training && <> using {run.details.training.real_rows} of your students and {run.details.training.synthetic_rows} generated rows (model {run.details.training.model_version})</>}.</p>
                    {run.details.level_counts && <p>Levels: {Object.entries(run.details.level_counts).map(([k, v]) => `${k} ${v}`).join(', ')}.</p>}
                    {run.details.data_gaps && Object.keys(run.details.data_gaps).length > 0 && <p>Students with missing data: {Object.entries(run.details.data_gaps).map(([k, v]) => `${v} with ${k}`).join('; ')}.</p>}
                    <Rates title="Flag rate by gender" f={run.fairness.gender} />
                    <Rates title="Flag rate by class" f={run.fairness.class} />
                    <p className="text-slate-500">This is a first look at who is flagged. It cannot show that the flags are fair, or that they are not.</p>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
