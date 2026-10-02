import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CalendarClock, ClipboardCheck, Handshake, UserPlus, Users } from 'lucide-react';
import hr, { Overview } from '@/services/hr.service';
import { card, fmtDate, PageHead, Pill, Spinner } from './ui';

const kindLabel = { contract_end: 'Contract', probation_end: 'Probation', credential: 'Credential' };

export default function HrOverviewPage() {
  const [o, setO] = useState<Overview | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { hr.overview().then(setO).catch(() => setFailed(true)); }, []);
  if (failed) return <p className="p-6 text-sm text-slate-500">The HR overview is only open to administrators, HR and managers.</p>;
  if (!o) return <Spinner />;

  const tiles = [
    { label: 'Active staff', value: o.staff, icon: Users, to: '/education/hr/directory' },
    { label: 'Out today', value: o.on_leave_today, icon: CalendarClock, to: '/education/hr/leave-calendar' },
    { label: 'Leave waiting for a decision', value: o.leave_waiting, icon: ClipboardCheck, to: '/education/timetable/leave' },
    { label: 'Periods needing cover', value: o.cover_open, icon: Handshake, to: '/education/hr/cover' },
    { label: 'Open positions', value: o.open_positions, icon: UserPlus, to: '/education/hr/recruitment' },
    { label: 'Candidates in progress', value: o.candidates_active, icon: UserPlus, to: '/education/hr/recruitment' },
    { label: 'New staff still onboarding', value: o.onboarding_open, icon: ClipboardCheck, to: '/education/hr/recruitment?tab=onboarding' },
    { label: 'Reviews still in draft', value: o.reviews_draft, icon: ClipboardCheck, to: '/education/hr/performance' },
  ];

  return (
    <div className="p-4 sm:p-6 space-y-5">
      <PageHead title="Staff & HR" hint="Everything about the people who work at the school: who is out, who covers, hiring, contracts, reviews and pay." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tiles.map((t) => (
          <Link key={t.label} to={t.to} className={`${card} hover:border-emerald-400 transition-colors`}>
            <t.icon className="w-4 h-4 text-emerald-700 mb-2" />
            <p className="text-2xl font-black text-slate-900">{t.value}</p>
            <p className="text-xs text-slate-500">{t.label}</p>
          </Link>
        ))}
      </div>

      <div className={card}>
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className={`w-4 h-4 ${o.expired ? 'text-rose-600' : 'text-amber-600'}`} />
          <h2 className="font-bold text-sm">Contracts and credentials needing attention</h2>
          <span className="text-xs text-slate-500">next 60 days{o.expired ? `, ${o.expired} already expired` : ''}</span>
          <Link to="/education/hr/records" className="ml-auto text-xs font-bold text-emerald-700">Open records</Link>
        </div>
        {o.alerts.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing is due. Contracts, probations and credentials are all current.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {o.alerts.map((a, i) => (
              <li key={i} className="py-2 flex flex-wrap items-center gap-2">
                <span className="font-semibold">{a.teacher_name}</span>
                <span className="text-slate-500">{kindLabel[a.kind]}: {a.what}</span>
                <span className="ml-auto flex items-center gap-2">
                  <span className="text-xs text-slate-500">{fmtDate(a.date)}</span>
                  <Pill tone={a.expired ? 'red' : a.days_left <= 14 ? 'amber' : 'blue'}>
                    {a.expired ? `ended ${-a.days_left} d ago` : `in ${a.days_left} d`}
                  </Pill>
                </span>
              </li>
            ))}
          </ul>
        )}
        {o.alert_count > o.alerts.length && <p className="text-xs text-slate-500 mt-2">And {o.alert_count - o.alerts.length} more in Records.</p>}
      </div>
    </div>
  );
}
