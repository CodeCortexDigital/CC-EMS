import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import hr, { CalendarLeave, leaveTypeLabel, LeaveCalendar } from '@/services/hr.service';
import { card, PageHead, Pill, Spinner, todayStr } from './ui';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/** Month grid starting on Monday: every day from the Monday on or before the 1st to the Sunday on or after the last. */
function gridDays(year: number, month: number): Date[] {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - ((first.getDay() + 6) % 7));
  const last = new Date(year, month + 1, 0);
  const end = new Date(year, month + 1, 0 + ((7 - ((last.getDay() + 6) % 7) - 1) % 7));
  const days: Date[] = [];
  for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) days.push(new Date(d));
  return days;
}

export default function LeaveCalendarPage() {
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() });
  const [data, setData] = useState<LeaveCalendar | null>(null);
  const days = useMemo(() => gridDays(ym.y, ym.m), [ym]);

  useEffect(() => {
    setData(null);
    hr.leave.calendar(iso(days[0]), iso(days[days.length - 1])).then(setData).catch(() => setData({ start: '', end: '', holidays: [], leaves: [] }));
  }, [days]);

  const byDay = useMemo(() => {
    const m = new Map<string, CalendarLeave[]>();
    (data?.leaves || []).forEach((l) => {
      for (const d = new Date(`${l.start_date}T00:00:00`); iso(d) <= l.end_date; d.setDate(d.getDate() + 1)) {
        m.set(iso(d), [...(m.get(iso(d)) || []), l]);
      }
    });
    return m;
  }, [data]);
  const holidays = useMemo(() => new Set(data?.holidays || []), [data]);
  const title = new Date(ym.y, ym.m, 1).toLocaleDateString([], { month: 'long', year: 'numeric' });
  const move = (n: number) => setYm((p) => { const d = new Date(p.y, p.m + n, 1); return { y: d.getFullYear(), m: d.getMonth() }; });
  const today = todayStr();

  return (
    <div className="p-4 sm:p-6">
      <PageHead title="Who is out" hint="Approved leave for the whole staff. Requests still waiting for a decision show with a dashed outline to administrators, managers and HR.">
        <div className="flex items-center gap-2">
          <button aria-label="Previous month" className="p-2 rounded-lg border border-slate-300" onClick={() => move(-1)}><ChevronLeft className="w-4 h-4" /></button>
          <span className="font-bold text-sm w-40 text-center">{title}</span>
          <button aria-label="Next month" className="p-2 rounded-lg border border-slate-300" onClick={() => move(1)}><ChevronRight className="w-4 h-4" /></button>
        </div>
      </PageHead>

      {!data ? <Spinner /> : (
        <div className={`${card} p-0 overflow-x-auto`}>
          <div className="min-w-[44rem]">
            <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50 text-xs font-bold text-slate-500">
              {DAYS.map((d) => <div key={d} className="px-2 py-1.5">{d}</div>)}
            </div>
            <div className="grid grid-cols-7">
              {days.map((d) => {
                const key = iso(d);
                const out = byDay.get(key) || [];
                const inMonth = d.getMonth() === ym.m;
                const weekend = d.getDay() === 0 || d.getDay() === 6;
                return (
                  <div key={key} className={`min-h-[6.5rem] border-b border-r border-slate-100 p-1.5 ${inMonth ? '' : 'bg-slate-50/60 text-slate-400'} ${holidays.has(key) ? 'bg-sky-50' : weekend ? 'bg-slate-50' : ''}`}>
                    <p className={`text-xs font-bold mb-1 ${key === today ? 'inline-block rounded-full bg-emerald-600 text-white px-1.5' : ''}`}>{d.getDate()}</p>
                    {holidays.has(key) && <p className="text-[10px] font-bold text-sky-700">School closed</p>}
                    <div className="space-y-0.5">
                      {out.slice(0, 4).map((l) => (
                        <p key={l.id + key} title={`${l.name}: ${leaveTypeLabel(l.leave_type)}${l.day_part !== 'full' ? ` (${l.day_part === 'am' ? 'morning' : 'afternoon'})` : ''}`}
                          className={`truncate rounded px-1 text-[11px] font-semibold ${l.status === 'approved' ? 'bg-emerald-100 text-emerald-900' : 'border border-dashed border-amber-400 text-amber-800'}`}>
                          {l.name.split(' ')[0]}{l.day_part !== 'full' ? ` ${l.day_part.toUpperCase()}` : ''}
                        </p>
                      ))}
                      {out.length > 4 && <p className="text-[10px] text-slate-500">+{out.length - 4} more</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2 mt-3 text-xs"><Pill tone="green">Approved</Pill><Pill tone="amber">Waiting (reviewers only)</Pill><Pill tone="blue">School closed</Pill></div>
    </div>
  );
}
