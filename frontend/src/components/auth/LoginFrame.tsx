// The sign-in page frame (the CC-IMS look): a calm mint page with flowing lines, the brand at the top left, a light/dark switch and a
// console pill at the top right, a large headline with a short "what you get" card on the left (large screens) and the sign-in card on the right.
// System fonts only, so the page looks the same offline.
import { useEffect, useState, type ReactNode } from 'react';
import { GraduationCap, LayoutDashboard, Moon, ShieldCheck, Sparkles, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { readThemeSettings, saveThemeSettings } from '@/utils/theme';
import { LanguageMenuButton } from '@/components/common/LanguagePicker';
import { useLocaleStore } from '@/store/localeStore';

export const SERIF = "font-['Cambria','Constantia','Palatino_Linotype',Georgia,serif]";
export const MONO = "font-['Cascadia_Mono',Consolas,'Courier_New',monospace]";

const greeting = (hour: number) => (hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening');

/** Sun on the left, moon on the right, a teal circle slides to the chosen side. Uses the app's theme, so the choice carries into the app. */
export function ThemeSwitch() {
  const [themeMode, setThemeMode] = useState(() => readThemeSettings().themeMode);
  useEffect(() => {
    const sync = () => setThemeMode(readThemeSettings().themeMode);
    window.addEventListener('theme-changed', sync);
    return () => window.removeEventListener('theme-changed', sync);
  }, []);
  const dark = themeMode === 'dark';
  const choose = (mode: 'light' | 'dark') => { setThemeMode(mode); saveThemeSettings({ themeMode: mode }); };
  return (
    <button type="button" role="switch" aria-checked={dark} aria-label="Dark mode" onClick={() => choose(dark ? 'light' : 'dark')}
      className="relative flex h-11 w-[5.2rem] items-center justify-between rounded-full bg-white px-3 shadow-[0_6px_20px_-10px_rgba(15,81,67,.5)] dark:bg-slate-800">
      <span aria-hidden className={`absolute top-1 h-9 w-9 rounded-full bg-[var(--app-accent)] transition-all duration-200 ${dark ? 'left-[2.75rem]' : 'left-1'}`} />
      <Sun className={`relative z-10 h-4 w-4 ${dark ? 'text-slate-400' : 'text-white'}`} />
      <Moon className={`relative z-10 h-4 w-4 ${dark ? 'text-white' : 'text-slate-400'}`} />
    </button>
  );
}

function FlowingLines() {
  return (
    <svg aria-hidden className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1440 900" preserveAspectRatio="none">
      {['M-60,640 C180,560 420,760 720,650 S1180,540 1500,630', 'M-60,700 C220,640 460,820 760,720 S1200,620 1500,700',
        'M-60,560 C160,480 440,660 700,560 S1160,450 1500,540', 'M-60,260 C200,200 420,340 700,260 S1160,170 1500,250',
        'M-60,330 C240,270 460,420 760,330 S1200,240 1500,320', 'M-60,120 C220,70 460,190 740,120 S1180,40 1500,110',
        'M-60,820 C260,760 500,880 800,810 S1220,740 1500,800'].map((d) => (
        <path key={d} d={d} fill="none" stroke="#2f8f7a" strokeWidth="1.2" className="opacity-20 dark:opacity-[0.08]" />
      ))}
    </svg>
  );
}

export default function LoginFrame({ children, console: consoleLabel }: { children: ReactNode; console: string }) {
  const { t } = useTranslation();
  const [hello, setHello] = useState('Welcome');
  const { userLanguage, school, setUserLanguage } = useLocaleStore();
  useEffect(() => setHello(greeting(new Date().getHours())), []);       // set after mount so the server and browser agree

  const gets: { icon: typeof LayoutDashboard; title: string; text: string }[] = [
    { icon: LayoutDashboard, title: t('auth.getOne', { defaultValue: 'Everything in one workspace' }), text: t('auth.getOneText', { defaultValue: 'Students, staff, fees, attendance and results, each role with its own portal.' }) },
    { icon: ShieldCheck, title: t('auth.getTwo', { defaultValue: 'Each school kept separate' }), text: t('auth.getTwoText', { defaultValue: 'People see only their own school and only what their role allows.' }) },
    { icon: Sparkles, title: t('auth.getThree', { defaultValue: 'AI that asks first' }), text: t('auth.getThreeText', { defaultValue: 'The assistant drafts and suggests. A person approves before anything is done.' }) },
  ];

  return (
    <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#e8f1ee_0%,#dcebe6_52%,#eef5f1_100%)] text-slate-800 dark:bg-none dark:bg-slate-950 dark:text-slate-100">
      <FlowingLines />
      <div className="relative mx-auto flex min-h-screen max-w-[1400px] flex-col px-6 py-8 sm:px-10 lg:px-16">
        <header className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--app-accent)] text-white shadow-[0_8px_18px_-8px_rgba(11,110,102,.7)]"><GraduationCap className="h-6 w-6" /></span>
            <div>
              <p className={`${SERIF} text-xl uppercase tracking-wide text-[var(--app-accent-strong)] dark:text-[var(--app-accent-text)]`}>Code Cortex</p>
              <p className={`${MONO} text-[10px] uppercase tracking-[0.32em] text-slate-500`}>Education management system</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <LanguageMenuButton value={userLanguage || school.language || 'en'} onChange={(code) => code && setUserLanguage(code)}
              buttonClassName="h-10 rounded-full bg-white px-3 text-slate-700 shadow-[0_6px_20px_-10px_rgba(15,81,67,.5)] hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-100" />
            <ThemeSwitch />
            <div className="hidden items-center gap-3 rounded-full bg-white px-3 py-2 shadow-[0_6px_20px_-10px_rgba(15,81,67,.5)] dark:bg-slate-800 sm:flex">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--app-accent)] text-white"><ShieldCheck className="h-5 w-5" /></span>
              <div className="leading-tight">
                <p className="text-[15px] font-semibold text-slate-900 dark:text-white">CC-EMS</p>
                <p className={`${MONO} text-[10px] uppercase tracking-[0.3em] text-slate-500`}>{consoleLabel}</p>
              </div>
              <span className="mr-1 h-3 w-3 rounded-full bg-emerald-500 ring-4 ring-emerald-200/70" />
            </div>
          </div>
        </header>

        <main className="grid flex-1 items-center gap-10 py-8 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
          <section className="hidden lg:block">
            <p className={`${MONO} flex items-center gap-3 text-xs uppercase tracking-[0.3em] text-[var(--app-accent)]`}>
              <span className="h-px w-8 bg-[var(--app-accent)]" />{hello} · {consoleLabel}
            </p>
            <h1 className={`${SERIF} mt-6 text-[4.4rem] font-normal leading-[1.05] tracking-tight text-slate-900 dark:text-white`}>
              {t('auth.headA', { defaultValue: 'Everything your school' })}<br />
              <span className="italic text-[var(--app-accent)]">{t('auth.headB', { defaultValue: 'runs on,' })}</span><br />
              {t('auth.headC', { defaultValue: 'in one place.' })}
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-slate-600 dark:text-slate-300">
              {t('auth.lead', { defaultValue: 'Sign in to see your classes, approvals and people in one calm workspace. Welcome to Code Cortex.' })}
            </p>
            <div className="mt-8 max-w-xl rounded-[26px] bg-white/70 p-6 shadow-[0_20px_60px_-30px_rgba(15,81,67,.35)] backdrop-blur dark:bg-slate-900/70">
              <p className={`${SERIF} border-b border-slate-200 pb-3 text-xl text-slate-900 dark:border-slate-700 dark:text-white`}>{t('auth.whatYouGet', { defaultValue: 'What you get' })}</p>
              <ul className="mt-4 space-y-4">
                {gets.map(({ icon: Icon, title, text }) => (
                  <li key={title} className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--app-accent-light)] text-[var(--app-accent-text)]"><Icon className="h-5 w-5" /></span>
                    <div><p className="font-semibold text-slate-900 dark:text-white">{title}</p><p className="text-sm text-slate-500 dark:text-slate-400">{text}</p></div>
                  </li>
                ))}
              </ul>
            </div>
          </section>
          <section className="mx-auto w-full max-w-[560px] lg:max-w-none lg:justify-self-end">
            <div className="rounded-[26px] bg-white px-7 py-8 shadow-[0_30px_80px_-34px_rgba(15,81,67,.4)] dark:bg-slate-900 sm:px-9">{children}</div>
          </section>
        </main>
      </div>
    </div>
  );
}
