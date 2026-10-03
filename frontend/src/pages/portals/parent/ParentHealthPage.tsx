import { useEffect, useState } from 'react';
import { Pill as PillIcon, Stethoscope } from 'lucide-react';
import { card, Empty, fmtDateTime, PageHead, Pill, Spinner } from '@/components/common/kit';
import health, { ACTIONS, HealthVisit, MedicationAuthorization, VISIT_TYPES } from '@/services/health.service';

/** What a parent can see: their own children's nurse visits and medication at school (read only). */
export default function ParentHealthPage() {
  const [visits, setVisits] = useState<HealthVisit[] | null>(null);
  const [meds, setMeds] = useState<MedicationAuthorization[] | null>(null);

  useEffect(() => {
    health.visits().then(setVisits).catch(() => setVisits([]));
    health.authorizations().then(setMeds).catch(() => setMeds([]));
  }, []);

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <PageHead title="Health at school" hint="Visits to the school nurse and the medicine the school may give. To change medication, contact the school office." />
      {visits === null || meds === null ? <Spinner /> : (
        <>
          <section aria-label="Medication">
            <h2 className="font-bold text-sm mb-2">Medication</h2>
            {meds.length === 0 ? <Empty>No medication on file.</Empty> : (
              <ul className="space-y-2">
                {meds.map((a) => (
                  <li key={a.id} className={card}>
                    <div className="flex flex-wrap items-center gap-2">
                      <PillIcon className="w-4 h-4 text-emerald-700" />
                      <b className="text-sm">{a.medication_name}</b> <span className="text-sm text-slate-500">{a.dose}{a.times && ` · ${a.times}`}</span>
                      <span className="text-sm">for <b>{a.student_name}</b></span>
                      <span className="ml-auto">{a.is_current ? <Pill tone="green">current</Pill> : <Pill tone="slate">not active</Pill>}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">From {a.start_date}{a.end_date && ` to ${a.end_date}`}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Visits">
            <h2 className="font-bold text-sm mb-2">Visits to the nurse</h2>
            {visits.length === 0 ? <Empty>No visits recorded.</Empty> : (
              <ul className="space-y-2">
                {visits.map((v) => (
                  <li key={v.id} className={card}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Stethoscope className="w-4 h-4 text-emerald-700" />
                      <b className="text-sm">{v.student_name}</b>
                      <Pill tone="blue">{VISIT_TYPES.find(([k]) => k === v.visit_type)?.[1] || v.visit_type}</Pill>
                      {v.sent_home && <Pill tone="amber">sent home</Pill>}
                      <span className="text-xs text-slate-400 ml-auto">{fmtDateTime(v.time_in)}</span>
                    </div>
                    {v.complaint && <p className="text-sm mt-1">{v.complaint}</p>}
                    <p className="text-xs text-slate-500 mt-1">{ACTIONS.find(([k]) => k === v.action_taken)?.[1]}{v.action_notes && ` · ${v.action_notes}`}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
