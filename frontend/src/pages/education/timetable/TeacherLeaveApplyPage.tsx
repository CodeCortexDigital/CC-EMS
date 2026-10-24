import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Calendar, UserX, CheckCircle2, Clock, Send } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Label } from '@/components/ui/Label';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { Input } from '@/components/ui/Input';
import teacherService from '@/services/teacher.service';
import hrService, { LEAVE_TYPES, leaveTypeLabel } from '@/services/hr.service';
import { useAuth } from '@/contexts/AuthContext';

export default function TeacherLeaveApplyPage() {
  const navigate = useNavigate();
  const { user, role } = useAuth();
  const [teacherId, setTeacherId] = useState<string | null>(null);
  const [teacherName, setTeacherName] = useState('');
  const [leaves, setLeaves] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({ leave_type: 'sick', day_part: 'full', start_date: '', end_date: '', reason: '' });
  const [previewDays, setPreviewDays] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [subsByLeave, setSubsByLeave] = useState<Record<string, any[]>>({});
  const [balance, setBalance] = useState<any | null>(null);

  const todayStr = () => new Date().toISOString().slice(0, 10);

  const resolveTeacherId = async (): Promise<string | null> => {
    // 1. Teachers: resolve via their own profile endpoint.
    if (role === 'teacher') {
      try {
        const profileRes = await teacherService.getMyProfile();
        const profile = profileRes?.data || profileRes;
        const id = profile?.id || profile?.teacher?.id;
        if (id) {
          setTeacherName(profile?.full_name || profile?.teacher?.full_name || '');
          return id;
        }
      } catch {
        /* not a teacher profile — fall through */
      }
    }
    // 2. Anyone (incl. staff/admin): match a linked teacher record by email.
    if (user?.email) {
      try {
        const matches = await teacherService.search(user.email);
        const list = Array.isArray(matches) ? matches : (matches?.data || []);
        const me = list.find(
          (t: any) => (t.email || '').toLowerCase() === user.email.toLowerCase()
        );
        if (me?.id) {
          setTeacherName(me.full_name || '');
          return me.id;
        }
      } catch {
        /* ignore */
      }
    }
    return null;
  };

  const loadProfileAndLeaves = async () => {
    setLoading(true);
    try {
      const id = await resolveTeacherId();
      if (id) {
        setTeacherId(id);
        const data = await teacherService.leaves.getAll({ teacher_id: id });
        setLeaves(Array.isArray(data) ? data : []);
        const bal = await teacherService.leaveBalances.get({ teacher_id: id });
        setBalance(bal);
      } else if (user?.email) {
        const data = await teacherService.leaves.getAll({ applicant_email: user.email });
        setLeaves(Array.isArray(data) ? data : []);
        const bal = await teacherService.leaveBalances.get({ applicant_email: user.email });
        setBalance(bal);
      }
    } catch (err) {
      console.error('Error loading profile/leaves:', err);
      setLeaves([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfileAndLeaves();
  }, []);

  const submitApplication = async () => {
    if (!form.start_date || !form.end_date) {
      setError('Start and end dates are required.');
      return;
    }
    const today = todayStr();
    if (form.start_date < today) {
      setError('Start date cannot be earlier than today.');
      return;
    }
    if (form.end_date < form.start_date) {
      setError('End date cannot be before the start date.');
      return;
    }
    // Prevent duplicate / overlapping leave for the same teacher.
    const conflict = leaves.find((l) => {
      if (l.status === 'cancelled' || l.status === 'rejected') return false;
      return form.start_date <= l.end_date && form.end_date >= l.start_date;
    });
    if (conflict) {
      setError('You already have a leave application overlapping these dates.');
      return;
    }
    setApplying(true);
    setError('');
    try {
      const payload: any = {
        leave_type: form.leave_type,
        day_part: form.start_date === form.end_date ? form.day_part : 'full',
        start_date: form.start_date,
        end_date: form.end_date,
        reason: form.reason,
        status: 'pending'
      };
      // Teaching staff are linked to a teacher record (enables automatic
      // substitution); other staff apply under their own name.
      if (teacherId) {
        payload.teacher = teacherId;
      } else {
        payload.applicant_name = user?.full_name || '';
        payload.applicant_email = user?.email || '';
      }
      await teacherService.leaves.create(payload);
      setModalOpen(false);
      setForm({ leave_type: 'sick', day_part: 'full', start_date: '', end_date: '', reason: '' });
      await loadProfileAndLeaves();
    } catch (err: any) {
      const d = err?.response?.data;
      setError(d?.error || (d && Object.values(d).flat().filter((x) => typeof x === 'string')[0] as string) || 'Failed to submit application.');
    } finally {
      setApplying(false);
    }
  };

  const cancelApplication = async (leaveId: string) => {
    try {
      await teacherService.leaves.remove(leaveId);
      await loadProfileAndLeaves();
      setExpanded(null);
    } catch (err) {
      console.error('Error cancelling application:', err);
    }
  };

  const toggleSubs = async (leaveId: string) => {
    if (expanded === leaveId) {
      setExpanded(null);
      return;
    }
    setExpanded(leaveId);
    if (!subsByLeave[leaveId]) {
      try {
        const subs = await teacherService.substitutions.getAll({ leave_id: leaveId });
        setSubsByLeave(prev => ({ ...prev, [leaveId]: Array.isArray(subs) ? subs : [] }));
      } catch {
        setSubsByLeave(prev => ({ ...prev, [leaveId]: [] }));
      }
    }
  };

  const statusVariant = (s: string) => {
    if (s === 'approved') return 'success';
    if (s === 'pending') return 'warning';
    if (s === 'recommended') return 'info';
    return 'secondary';
  };

  useEffect(() => {
    if (form.start_date && form.end_date && form.end_date >= form.start_date) {
      hrService.leave.days(form.start_date, form.end_date, form.start_date === form.end_date ? form.day_part : 'full')
        .then(setPreviewDays).catch(() => setPreviewDays(null));
    } else {
      setPreviewDays(null);
    }
  }, [form.start_date, form.end_date, form.day_part]);

  const pendingCount = useMemo(() => leaves.filter(l => l.status === 'pending').length, [leaves]);

  return (
    <div className="space-y-3 pb-4 text-slate-800">
      <div className="flex items-center justify-between bg-white p-3.5 rounded-xl border border-slate-100 shadow-xs">
        <div className="flex items-center gap-2 text-xs font-semibold text-purple-700">
          <Calendar className="w-4 h-4 text-purple-700" />
          <span className="cursor-pointer hover:underline" onClick={() => navigate('/education/timetable')}>Timetable</span>
          <span>&gt;</span>
          <span className="text-slate-500 font-bold">My Leave</span>
        </div>
        <button
          onClick={() => navigate('/education/timetable/view')}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
      </div>

      <div className="max-w-3xl mx-auto space-y-6">
        {balance && (
          <div className="flex items-center justify-between bg-white border border-slate-100 shadow-sm rounded-xl p-4">
            <div>
              <p className="text-xs font-bold text-slate-700">Leave Balance</p>
              <p className="text-[10px] text-slate-400 font-semibold">
                {balance.used_days} working day(s) used this year
              </p>
              <p className="text-[10px] text-slate-400 font-semibold mt-1">
                {LEAVE_TYPES.filter((t) => (balance.balance_by_type?.[t.key] ?? 0) > 0 || (balance.used_by_type?.[t.key] ?? 0) > 0).map((t) => `${t.label}: ${balance.balance_by_type?.[t.key] ?? 0} left`).join(' · ')}
              </p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-black text-purple-650">{balance.balance_days}</p>
              <p className="text-[10px] text-slate-400 font-semibold">days remaining</p>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-base font-bold text-slate-800 flex items-center gap-2">
              <UserX className="w-5 h-5 text-purple-650" /> My Leave Applications
            </h1>
            <p className="text-[10px] text-slate-400 font-bold">
              Apply for leave in advance. Once approved by admin, your periods are auto-covered by an available relief teacher.
            </p>
          </div>
          <Button onClick={() => { setError(''); setModalOpen(true); }} className="flex items-center gap-1.5">
            <Send className="w-4 h-4" /> Apply for Leave
          </Button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
          </div>
        ) : (
          <>
            {!teacherId && (
              <Card className="p-3 text-xs text-slate-500 font-semibold bg-amber-50 border border-amber-200">
                No teaching profile is linked to your account. Your leave will be recorded as staff leave
                (no automatic timetable substitution).
              </Card>
            )}
            <div className="space-y-3">
            {leaves.length === 0 ? (
              <Card className="p-6 text-center text-xs text-slate-400 font-semibold">
                No leave applications yet.
              </Card>
            ) : (
              leaves.map(l => (
                <div key={l.id} className="border border-slate-100 rounded-xl bg-white overflow-hidden">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center">
                        <UserX className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-sm font-bold text-slate-800">{leaveTypeLabel(l.leave_type)}{l.day_part === 'am' ? ' (morning)' : l.day_part === 'pm' ? ' (afternoon)' : ''}</p>
                        <p className="text-[10px] text-slate-400 font-semibold">
                          {l.applicant_display ? `${l.applicant_display} · ` : ''}{l.start_date} → {l.end_date} · {l.days} working day(s)
                        </p>
                        {l.status === 'recommended' && <p className="text-[10px] text-sky-600 font-semibold">Recommended by {l.recommended_by}; waiting for final approval.</p>}
                        {l.decision_note && <p className="text-[10px] text-slate-500 font-semibold">Note: {l.decision_note}</p>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={statusVariant(l.status)}>{l.status}</Badge>
                      {l.substitute_assigned && (
                        <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1" />Covered</Badge>
                      )}
                      <Button variant="outline" className="h-8 px-3 text-xs" onClick={() => toggleSubs(l.id)}>
                        {expanded === l.id ? 'Hide' : 'Substitutions'}
                      </Button>
                      {(l.status === 'pending' || l.status === 'recommended') && (
                        <Button variant="destructive" className="h-8 px-3 text-xs" onClick={() => cancelApplication(l.id)}>
                          Withdraw
                        </Button>
                      )}
                    </div>
                  </div>
                  {expanded === l.id && (
                    <div className="border-t bg-slate-50 p-4">
                      {(subsByLeave[l.id] || []).length === 0 ? (
                        <p className="text-xs text-slate-500 font-semibold">
                          {l.status === 'approved'
                            ? 'None of your periods fall on the days of this leave, or no cover is arranged yet.'
                            : 'Substitutions will be assigned after admin approval.'}
                        </p>
                      ) : (
                        <div className="overflow-x-auto border rounded-lg bg-white">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 text-slate-500 uppercase text-[9px]">
                              <tr>
                                <th className="p-2.5">Date</th>
                                <th className="p-2.5">Period</th>
                                <th className="p-2.5">Subject</th>
                                <th className="p-2.5">Covered by</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                              {subsByLeave[l.id].map((s) => (
                                <tr key={s.id}>
                                  <td className="p-2.5 font-bold">{s.date ? new Date(`${s.date}T00:00:00`).toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' }) : s.day_of_week}</td>
                                  <td className="p-2.5">{s.period_name}</td>
                                  <td className="p-2.5">{s.subject_name}</td>
                                  <td className="p-2.5">{s.relief_teacher_name || <span className="text-amber-600 font-bold">Looking for cover</span>}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
            </div>
          </>
        )}
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Apply for Leave"
        description="Your application will be sent to the admin for approval. Timetable coverage is arranged only after approval."
      >
        <div className="space-y-4">
          <div>
            <Label className="text-xs">Leave Type</Label>
            <Select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
              {LEAVE_TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Start Date</Label>
              <Input type="date" min={todayStr()} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </div>
            <div>
              <Label className="text-xs">End Date</Label>
              <Input type="date" min={form.start_date || todayStr()} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
            </div>
          </div>
          {form.start_date && form.start_date === form.end_date && (
            <div>
              <Label className="text-xs">Which part of the day</Label>
              <Select value={form.day_part} onChange={(e) => setForm({ ...form, day_part: e.target.value })}>
                <option value="full">Full day</option>
                <option value="am">Morning only (half day)</option>
                <option value="pm">Afternoon only (half day)</option>
              </Select>
            </div>
          )}
          <div>
            <Label className="text-xs">Reason</Label>
            <Textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Optional" />
          </div>
          {form.start_date && form.end_date && (() => {
            const days = previewDays ?? 0;
            const typeBalance = balance?.balance_by_type?.[form.leave_type];
            const remaining = balance && form.leave_type !== 'unpaid' && typeof typeBalance === 'number' ? typeBalance - days : null;
            return (
              <div className={`text-xs font-semibold rounded-lg p-2.5 ${remaining !== null && remaining < 0 ? 'bg-red-50 text-red-600' : 'bg-slate-50 text-slate-600'}`}>
                Requesting <b>{days}</b> working day(s) <span className="font-normal">(weekends and school holidays are not counted)</span>
                {balance && remaining !== null ? (
                  <>
                    . Left of {leaveTypeLabel(form.leave_type).toLowerCase()} leave after this: <b>{remaining}</b> day(s)
                    {remaining < 0 && ' — more than you have left; the office may still approve it.'}
                  </>
                ) : (
                  ' — set your leave limits in admin to see remaining balance.'
                )}
              </div>
            );
          })()}
          {error && <p className="text-xs text-red-600 font-semibold">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={submitApplication} disabled={applying}>
              {applying ? 'Submitting...' : 'Submit Application'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
