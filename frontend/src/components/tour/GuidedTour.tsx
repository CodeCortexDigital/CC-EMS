// The guided tour: opens at every sign-in until the person has been through every step. "Skip" hides it for the rest of that sign-in only;
// it comes back at the next sign-in. It can also be replayed from Help.
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/hooks/useAuth';
import { tourFor } from '@/config/tourSteps';
import tourApi, { needsTour, skippedThisSignIn, skipForThisSignIn, START_TOUR_EVENT } from '@/services/tour.service';

export default function GuidedTour() {
  const { role } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const tour = tourFor(role);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  // Show it automatically until this version has been finished (unless it was skipped during this sign-in).
  useEffect(() => {
    if (!tour || skippedThisSignIn(tour.key)) return;
    let cancelled = false;
    tourApi.progress()
      .then((p) => { if (!cancelled && needsTour(p, tour.key, tour.version)) { setStep(0); setOpen(true); } })
      .catch(() => undefined);               // if we cannot tell, do not nag
    return () => { cancelled = true; };
  }, [tour?.key, tour?.version]);            // eslint-disable-line react-hooks/exhaustive-deps

  // "Take the tour" buttons elsewhere in the app.
  useEffect(() => {
    const start = () => { if (tour) { setStep(0); setOpen(true); } };
    window.addEventListener(START_TOUR_EVENT, start);
    return () => window.removeEventListener(START_TOUR_EVENT, start);
  }, [tour]);

  const finish = useCallback((status: 'completed' | 'skipped') => {
    setOpen(false);
    if (!tour) return;
    if (status === 'skipped') skipForThisSignIn(tour.key);
    tourApi.record(tour.key, tour.version, status).catch(() => undefined);
  }, [tour]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') finish('skipped'); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, finish]);

  if (!tour || !open) return null;
  const current = tour.steps[step];
  const last = step === tour.steps.length - 1;

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Guided tour">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl p-5">
        <div className="flex items-start gap-3">
          <div className="mr-auto">
            <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-700">{t('tour.stepOf', { defaultValue: 'Step {{current}} of {{total}}', current: step + 1, total: tour.steps.length })}</p>
            <h2 className="text-lg font-black text-slate-900 mt-0.5">{current.title}</h2>
          </div>
          <button aria-label="Skip the tour" className="text-slate-400 hover:text-slate-700" onClick={() => finish('skipped')}><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-slate-600 mt-2 leading-relaxed">{current.body}</p>

        <div className="flex gap-1 mt-4" aria-hidden="true">
          {tour.steps.map((_, i) => <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-emerald-600' : 'bg-slate-200'}`} />)}
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4">
          {current.href && (
            <button className="text-xs font-bold text-emerald-700 underline mr-auto" onClick={() => { navigate(current.href!); }}>{current.linkLabel || 'Go there'}</button>
          )}
          <span className="ml-auto flex gap-2">
            {step > 0 && <button className="px-3 py-2 rounded-lg text-xs font-bold border border-slate-300 text-slate-700" onClick={() => setStep(step - 1)}>Back</button>}
            {!last && <button className="px-3 py-2 rounded-lg text-xs font-bold text-slate-500" onClick={() => finish('skipped')}>Skip</button>}
            <button className="px-3 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white" onClick={() => (last ? finish('completed') : setStep(step + 1))}>{last ? 'Finish' : 'Next'}</button>
          </span>
        </div>
      </div>
    </div>
  );
}
