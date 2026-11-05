import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import {
  User, Lock, Eye, EyeOff, ShieldCheck, GraduationCap, Briefcase, AlertCircle, ArrowRight, Loader2, School,
  HelpCircle, UserPlus, LayoutDashboard, Sparkles,
} from 'lucide-react';
import { GoogleMark } from '@/components/auth/AuthShell';
import LoginFrame, { SERIF } from '@/components/auth/LoginFrame';
import { Modal } from '@/components/ui/Modal';
import schoolService from '@/services/school.service';
import api from '@/services/api';
import { useTranslation } from 'react-i18next';
import { TwoStepNeeded } from '@/store/authStore';
import TwoStepCodeForm from '@/components/auth/TwoStepCodeForm';

type LoginRole = 'admin' | 'employee' | 'student';

const ROLES: { id: LoginRole; label: string; icon: typeof User }[] = [
  { id: 'admin', label: 'auth.roleAdmin', icon: ShieldCheck },
  { id: 'employee', label: 'auth.roleStaff', icon: Briefcase },
  { id: 'student', label: 'auth.roleStudentParent', icon: GraduationCap },
];

// What to type depends on who is signing in; the server decides the portal.
const HINTS: Record<LoginRole, { placeholder: string; hint: string }> = {
  admin: { placeholder: 'admin@school.com', hint: 'auth.hintAdmin' },
  employee: { placeholder: 'EMP-001', hint: 'auth.hintStaff' },
  student: { placeholder: 'GVS-2026-001', hint: 'auth.hintStudent' },
};

const REMEMBER_KEY = 'login_remembered_username';

// Demo accounts: shown only on a demo site, where VITE_DEMO_LOGINS=true is set in the build environment (never on a live site).
const SHOW_DEMO_LOGINS = import.meta.env.VITE_DEMO_LOGINS === 'true';
const DEMO_LOGINS: { label: string; email: string; password: string; role: LoginRole }[] = [
  { label: 'Admin', email: 'admin@code.com', password: 'Admin@123', role: 'admin' },
  { label: 'Teacher', email: 'teacher@code.com', password: 'Teacher@123', role: 'employee' },
  { label: 'Parent', email: 'parent@code.com', password: 'Parent@123', role: 'student' },
  { label: 'Student', email: 'student@code.com', password: 'Student@123', role: 'student' },
];

function MicrosoftMark() {
  return (
    <svg aria-hidden viewBox="0 0 21 21" className="w-4 h-4"><rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect x="1" y="11" width="9" height="9" fill="#00a4ef" /><rect x="11" y="11" width="9" height="9" fill="#ffb900" /></svg>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, googleLogin, ssoLogin, completeTwoStep } = useAuth();
  const [params, setParams] = useSearchParams();
  const { t } = useTranslation();
  const [role, setRole] = useState<LoginRole>('admin');
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [msOpen, setMsOpen] = useState(false);
  const [msEmail, setMsEmail] = useState('');
  const [msLoading, setMsLoading] = useState(false);
  const [error, setError] = useState('');
  // Accounts with two-step sign-in: after the password (or Google / Microsoft) they enter a code (P8).
  const [twoStep, setTwoStep] = useState<TwoStepNeeded | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    try {
      // Older builds kept fake portal logins in the browser; they are never valid.
      localStorage.removeItem('staff_login_credentials');
      localStorage.removeItem('student_login_credentials');
      const remembered = localStorage.getItem(REMEMBER_KEY);
      if (remembered) {
        setUserId(remembered);
        setRememberMe(true);
      }
    } catch {
      /* storage unavailable */
    }
    schoolService.signupConfig().then((c) => setGoogleEnabled(c.google_sign_in)).catch(() => setGoogleEnabled(false));
  }, []);

  // A calm full-page message while the first page loads, then on to the portal.
  const goToPortal = (authUser: any) => {
    const target = authUser?.portal_path || (authUser?.role === 'student' ? '/student' : '/dashboard');
    setRedirecting(true);
    window.setTimeout(() => navigate(target), 1800);
  };

  // Coming back from "Sign in with Microsoft": swap the one-time code for a session, or show why it failed.
  useEffect(() => {
    const code = params.get('sso');
    const ssoError = params.get('sso_error');
    if (!code && !ssoError) return;
    setParams({}, { replace: true });
    if (ssoError) { setError(ssoError); return; }
    setMsLoading(true);
    ssoLogin(code!).then(goToPortal).catch((err: any) => (err instanceof TwoStepNeeded ? setTwoStep(err) : setError(err?.response?.data?.error || t('auth.errorMicrosoft'))))
      .finally(() => setMsLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMicrosoft = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const email = (msEmail || (userId.includes('@') ? userId : '')).trim();
    if (!email.includes('@')) { setMsOpen(true); return; }
    setError('');
    setMsLoading(true);
    try {
      const r = await api.post<{ url: string }>('/auth/integrations/microsoft/start/', { email, origin: window.location.origin });
      window.location.assign(r.data.url);
    } catch (err: any) {
      setError(err?.response?.data?.error || t('auth.errorMicrosoft'));
      setMsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim() || !password) {
      setError(t('auth.errorEmpty'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      const authUser = await login(userId.trim(), password);
      try {
        if (rememberMe) localStorage.setItem(REMEMBER_KEY, userId.trim());
        else localStorage.removeItem(REMEMBER_KEY);
      } catch {
        /* storage unavailable */
      }
      goToPortal(authUser);
    } catch (err: any) {
      if (err instanceof TwoStepNeeded) { setTwoStep(err); return; }
      const status = err.response?.status;
      setError(
        err.response?.data?.error ||
          (status === 401 ? t('auth.errorWrong') : '') ||
          (err.message === 'Network Error' ? t('auth.errorNetwork') : err.message) ||
          t('auth.errorWrong')
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError('');
    setGoogleLoading(true);
    let idToken = '';
    try {
      const { signInWithGoogle } = await import('@/services/firebase');
      idToken = await signInWithGoogle();
      goToPortal(await googleLogin(idToken));
    } catch (err: any) {
      if (err instanceof TwoStepNeeded) { setTwoStep(err); return; }
      if (err?.response?.data?.needs_signup) {
        // New Google user: they can create their own school with this account.
        navigate('/signup', { state: { googleToken: idToken, email: err.response.data.email, name: err.response.data.name } });
        return;
      }
      if (err?.code === 'auth/popup-closed-by-user' || err?.code === 'auth/cancelled-popup-request') return;
      setError(err?.response?.data?.error || t('auth.errorGoogle'));
    } finally {
      setGoogleLoading(false);
    }
  };

  const { placeholder, hint } = HINTS[role];
  const consoleLabel = role === 'admin' ? 'Admin console' : role === 'employee' ? 'Staff console' : 'Family portal';
  const inputBase = 'h-16 w-full rounded-2xl border-2 border-[#dfe9e6] bg-[#f5faf8] px-5 text-[17px] text-slate-900 placeholder:text-[#a2b3ae] outline-none transition focus:border-[var(--app-accent)] focus:ring-4 focus:ring-[color:rgb(var(--app-accent-rgb)/0.1)] dark:border-slate-700 dark:bg-slate-800 dark:text-white';

  // After a good sign-in: a calm full-page message while the first page loads.
  if (redirecting) {
    return (
      <div role="status" className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[#eef4f4] dark:bg-slate-950">
        <span className="h-16 w-16 animate-spin rounded-full border-4 border-[color:rgb(var(--app-accent-rgb)/0.2)] border-t-[var(--app-accent)]" />
        <p className="text-xl font-semibold text-[var(--app-accent-strong)] dark:text-[var(--app-accent-text)]">Please wait while we are loading your login profile…</p>
      </div>
    );
  }

  if (twoStep) {
    return (
      <LoginFrame console={consoleLabel}>
        <TwoStepCodeForm
          email={twoStep.email}
          onSubmit={async (code) => goToPortal(await completeTwoStep(twoStep.challenge, code))}
          onRestart={() => { setTwoStep(null); setPassword(''); }}
        />
      </LoginFrame>
    );
  }

  return (
    <LoginFrame console={consoleLabel}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className={`${SERIF} text-[2rem] font-normal leading-tight text-slate-900 dark:text-white`}>{t('auth.signIn')}</h2>
          <p className="mt-1 text-[15px] text-[#8aa39d]">{t('auth.welcome')}</p>
        </div>
        <button type="button" onClick={() => setHelpOpen(true)}
          className="mt-1 flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
          <HelpCircle className="h-3.5 w-3.5" /> Help
        </button>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        {/* Who is signing in: one switch, three doors (the server decides the portal) */}
        <div role="radiogroup" aria-label={t('auth.iAm')} className="grid grid-cols-[1fr_1fr_1.4fr] gap-1 rounded-full border border-[#dbe7e3] bg-[#f5faf8] p-1 dark:border-slate-700 dark:bg-slate-800">
          {ROLES.map(({ id, label }) => {
            const active = role === id;
            return (
              <button key={id} type="button" role="radio" aria-checked={active} onClick={() => { setRole(id); setError(''); }}
                className={`whitespace-nowrap rounded-full px-3 py-2.5 text-[15px] font-semibold transition-all ${active ? 'bg-[var(--app-accent)] text-white shadow-sm' : 'text-[#4b6b66] hover:text-slate-900 dark:text-slate-300'}`}>
                {t(label)}
              </button>
            );
          })}
        </div>

        {error && (
          <div role="alert" className="flex items-start gap-2.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span>
          </div>
        )}

        <div>
          <label htmlFor="login-username" className="sr-only">{t('auth.username')}</label>
          <input id="login-username" type="text" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder={placeholder}
            autoComplete="off" autoCapitalize="none" spellCheck={false} aria-describedby="login-username-hint" className={inputBase} />
          <p id="login-username-hint" className="mt-1.5 px-1 text-xs text-[#8aa39d]">{t(hint)}</p>
        </div>

        <div className="relative">
          <label htmlFor="login-password" className="sr-only">{t('auth.password')}</label>
          <input id="login-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder={t('auth.passwordPlaceholder')} autoComplete="current-password" className={`${inputBase} pe-14`} />
          <button type="button" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? t('auth.hidePassword') : t('auth.showPassword')}
            className="absolute end-3 top-4 rounded-lg p-2 text-slate-400 hover:text-slate-700">
            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>

        <label className="flex cursor-pointer select-none items-center gap-2.5 text-[15px] text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="h-5 w-5 rounded border-slate-300 accent-[color:var(--app-accent)]" />
          {t('auth.remember')}
        </label>

        <div className="flex flex-wrap items-center gap-5 pt-1">
          <button type="submit" disabled={loading}
            className="inline-flex h-14 min-w-[168px] items-center justify-center gap-2 rounded-2xl bg-[var(--app-accent)] px-8 text-[17px] font-semibold text-white shadow-[0_10px_24px_-12px_rgba(11,110,102,.8)] transition hover:bg-[var(--app-accent-strong)] disabled:opacity-60">
            {loading ? (<><Loader2 className="h-4 w-4 animate-spin" /> {t('auth.signingIn')}</>) : 'Login'}
          </button>
          <Link to="/forgot-password" className="text-[17px] text-[#4b6b66] hover:underline dark:text-slate-300">{t('auth.forgotPassword')}</Link>
        </div>
      </form>

      {SHOW_DEMO_LOGINS && (
        <div className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900" aria-label="Demo accounts">
          <p className="mb-2 font-semibold">Demo school (sample data). Click an account to fill it in:</p>
          <ul className="space-y-1">
            {DEMO_LOGINS.map((a) => (
              <li key={a.email}>
                <button type="button" onClick={() => { setRole(a.role); setUserId(a.email); setPassword(a.password); setError(''); }}
                  className="w-full rounded-lg bg-white/70 px-2 py-1 text-start hover:bg-white">
                  <b>{a.label}</b>: <span className="font-mono">{a.email}</span> / <span className="font-mono">{a.password}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="my-6 flex items-center gap-3 text-xs text-slate-400">
        <span className="h-px flex-1 bg-slate-200" /> {t('common.or')} <span className="h-px flex-1 bg-slate-200" />
      </div>
      <div className="space-y-2">
        {googleEnabled && (
          <button type="button" onClick={handleGoogle} disabled={googleLoading} className="auth-secondary-btn !rounded-2xl">
            {googleLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleMark />}
            {t('auth.continueGoogle')}
          </button>
        )}
        {!msOpen ? (
          <button type="button" onClick={() => handleMicrosoft()} disabled={msLoading} className="auth-secondary-btn !rounded-2xl">
            {msLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MicrosoftMark />}
            {t('auth.continueMicrosoft')}
          </button>
        ) : (
          <form onSubmit={handleMicrosoft} className="flex gap-2">
            <input type="email" autoFocus required aria-label={t('auth.microsoftEmail')} placeholder={t('auth.microsoftEmail')} value={msEmail}
              onChange={(e) => setMsEmail(e.target.value)} className="flex-1 rounded-2xl border border-slate-300 px-3 py-2.5 text-sm" />
            <button type="submit" disabled={msLoading} className="auth-secondary-btn !w-auto !rounded-2xl px-4">
              {msLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MicrosoftMark />} {t('auth.microsoftContinue')}
            </button>
          </form>
        )}
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 text-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="flex items-center gap-2 font-semibold text-slate-800 dark:text-white"><School className="h-4 w-4 text-[var(--app-accent)]" /> {t('auth.runningSchool')}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">{t('auth.runningSchoolText')}</p>
        <Link to="/signup" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--app-accent)] hover:underline">
          {t('auth.createSchool')} <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />
        </Link>
      </div>
      <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs text-[#8aa39d]">
        <Lock className="h-3 w-3" /> Encrypted connection · every sign-in is logged
      </p>
      <p className="mt-2 text-center text-xs text-slate-500"><Link to="/legal/privacy" className="hover:underline">Privacy notice</Link> · <Link to="/legal/terms" className="hover:underline">Terms of use</Link></p>

      <Modal open={helpOpen} onClose={() => setHelpOpen(false)} title="How to try CC-EMS" size="lg">
        <div className="space-y-5 text-sm text-slate-700">
          <div className="flex gap-3">
            <UserPlus className="h-5 w-5 shrink-0 text-brand" />
            <div>
              <p className="font-semibold text-slate-800">1. Create your own school (recommended)</p>
              <p className="mt-1 text-slate-500">
                Click <Link to="/signup" onClick={() => setHelpOpen(false)} className="font-semibold text-brand hover:underline">Create your school</Link> below,
                or use "Continue with Google". You'll become that school's admin instantly, with a fresh, empty
                account — no data to worry about, nothing shared with anyone else.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <LayoutDashboard className="h-5 w-5 shrink-0 text-brand" />
            <div>
              <p className="font-semibold text-slate-800">2. Explore as admin</p>
              <p className="mt-1 text-slate-500">
                Add a class, a teacher and a few students from the setup checklist on your dashboard. From there you
                can try attendance, fees, exams, timetables, and the other modules in the top menu.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <Sparkles className="h-5 w-5 shrink-0 text-brand" />
            <div>
              <p className="font-semibold text-slate-800">3. Try the AI assistant</p>
              <p className="mt-1 text-slate-500">
                The button in the bottom-right corner of the dashboard answers questions about your school's
                own data — try "How many students are absent today?" once you've added some.
              </p>
            </div>
          </div>
          <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
            Questions about anything you see? Reply to the email this link came with and we'll help directly.
          </p>
        </div>
      </Modal>
    </LoginFrame>
  );
}
