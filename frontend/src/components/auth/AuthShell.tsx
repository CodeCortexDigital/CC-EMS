import { useEffect, useState, type ReactNode } from 'react';
import {
  ShieldCheck, GraduationCap, CalendarCheck, Wallet, Sparkles, UsersRound, Languages, Building2, Bot,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { LanguageMenuButton } from '@/components/common/LanguagePicker';
import { useLocaleStore } from '@/store/localeStore';

const FEATURES = [
  { icon: CalendarCheck, title: 'brand.f1Title', text: 'brand.f1Text' },
  { icon: Wallet, title: 'brand.f2Title', text: 'brand.f2Text' },
  { icon: Sparkles, title: 'brand.f3Title', text: 'brand.f3Text' },
  { icon: UsersRound, title: 'brand.f4Title', text: 'brand.f4Text' },
  { icon: Languages, title: 'brand.f5Title', text: 'brand.f5Text' },
  { icon: Building2, title: 'brand.f6Title', text: 'brand.f6Text' },
];

// Sample questions the assistant "answers" in the preview card (illustrative, not live data).
const ASSISTANT_DEMOS = [
  { q: 'brand.demo1Q', a: 'brand.demo1A' },
  { q: 'brand.demo2Q', a: 'brand.demo2A' },
  { q: 'brand.demo3Q', a: 'brand.demo3A' },
];

const STYLES = `
  @keyframes authRise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  @keyframes authFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
  @keyframes authPulse { 0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, .6); } 100% { box-shadow: 0 0 0 8px rgba(74, 222, 128, 0); } }
  @keyframes authFill { from { width: 0; } }
  @keyframes authRing { from { stroke-dashoffset: 100; } }
  .auth-rise { animation: authRise .5s ease both; }
  .auth-float { animation: authFloat 6s ease-in-out infinite; }
  .auth-live { animation: authPulse 1.6s ease-out infinite; }
  .auth-fill { animation: authFill 1.2s .3s ease-out both; }
  .auth-ring { animation: authRing 1.2s .3s ease-out both; }
  @media (prefers-reduced-motion: reduce) {
    .auth-rise, .auth-float, .auth-live, .auth-fill, .auth-ring { animation: none; }
  }
`;

/** Ring gauge for a percentage (0-100). */
function Ring({ value }: { value: number }) {
  return (
    <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90" aria-hidden="true">
      <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(255,255,255,.2)" strokeWidth="3.5" />
      <circle
        cx="18" cy="18" r="15.9" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round"
        pathLength={100} strokeDasharray="100" strokeDashoffset={100 - value} className="auth-ring"
      />
    </svg>
  );
}

/** A sample "today at a glance" card plus an assistant that cycles through example questions. */
function ProductPreview() {
  const { t } = useTranslation();
  const [demo, setDemo] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setDemo((i) => (i + 1) % ASSISTANT_DEMOS.length), 5500);
    return () => window.clearInterval(id);
  }, []);

  const current = ASSISTANT_DEMOS[demo];

  return (
    <div className="auth-float rounded-2xl bg-white/10 ring-1 ring-white/25 backdrop-blur-md p-4 shadow-xl shadow-black/10">
      <div className="flex items-center justify-between text-xs font-semibold text-white/80">
        <span className="flex items-center gap-2">
          <span className="auth-live w-2 h-2 rounded-full bg-green-400" />
          {t('brand.previewTitle')}
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-white/50">{t('brand.previewNote')}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="flex items-center gap-3 rounded-xl bg-white/10 p-3">
          <div className="relative shrink-0">
            <Ring value={96} />
            <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold">96%</span>
          </div>
          <p className="text-xs leading-snug text-white/80">{t('brand.previewAttendance')}</p>
        </div>
        <div className="rounded-xl bg-white/10 p-3">
          <p className="text-xs leading-snug text-white/80">{t('brand.previewFees')}</p>
          <p className="mt-1 text-lg font-bold leading-none">82%</p>
          <div className="mt-2 h-1.5 rounded-full bg-white/20 overflow-hidden">
            <div className="auth-fill h-full rounded-full bg-white" style={{ width: '82%' }} />
          </div>
        </div>
      </div>

      <div key={demo} className="auth-rise mt-3 space-y-2" aria-live="polite">
        <p className="ms-auto w-fit max-w-[85%] rounded-2xl rounded-ee-sm bg-white/20 px-3 py-1.5 text-xs">{t(current.q)}</p>
        <div className="flex items-start gap-2">
          <span className="shrink-0 w-6 h-6 rounded-full bg-white text-brand flex items-center justify-center">
            <Bot className="w-3.5 h-3.5" />
          </span>
          <p className="max-w-[85%] rounded-2xl rounded-ss-sm bg-white/10 px-3 py-1.5 text-xs text-white/90">{t(current.a)}</p>
        </div>
      </div>
    </div>
  );
}

/** Brand panel + centred form column shared by sign-in and school signup. */
export default function AuthShell({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { t, i18n } = useTranslation();
  const setUserLanguage = useLocaleStore((s) => s.setUserLanguage);

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-[var(--dk-page)]">
      <style>{STYLES}</style>
      <aside className="hidden lg:flex lg:w-[46%] xl:w-1/2 bg-brand-gradient relative overflow-hidden flex-col justify-between gap-8 p-10 xl:p-14">
        <div className="absolute inset-0 bg-dots opacity-60" aria-hidden="true" />
        <div className="absolute -top-24 -end-24 w-96 h-96 rounded-full bg-white/10 blur-sm" />
        <div className="absolute -bottom-32 -start-20 w-[28rem] h-[28rem] rounded-full bg-cyan-300/10 blur-2xl" />

        <div className="relative flex items-center gap-3">
          <span className="w-11 h-11 rounded-xl bg-white/15 ring-1 ring-white/25 flex items-center justify-center">
            <GraduationCap className="w-6 h-6" />
          </span>
          <div className="leading-tight">
            <p className="text-lg font-bold">Code Cortex</p>
            <p className="text-xs text-white/70">{t('brand.product')}</p>
          </div>
          <span className="ms-auto rounded-full bg-white/15 ring-1 ring-white/25 px-3 py-1 text-xs font-bold tracking-wider">CC-EMS</span>
        </div>

        <div className="relative max-w-lg space-y-7">
          <div>
            <h1 className="text-3xl xl:text-4xl font-extrabold leading-tight tracking-tight !text-white">
              {t('brand.headline')}
            </h1>
            <p className="mt-3 text-white/75 text-[15px] leading-relaxed">{t('brand.intro')}</p>
          </div>

          <ProductPreview />

          <ul className="grid grid-cols-2 gap-x-6 gap-y-5">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="shrink-0 w-9 h-9 rounded-xl bg-white/15 flex items-center justify-center">
                  <Icon className="w-[18px] h-[18px]" />
                </span>
                <div>
                  <p className="text-sm font-semibold leading-tight">{t(title)}</p>
                  <p className="mt-0.5 text-xs text-white/70 leading-snug">{t(text)}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative flex items-center gap-2 text-xs text-white/70">
          <ShieldCheck className="w-4 h-4" />
          {t('brand.secure')}
        </p>
      </aside>

      <main className="relative flex-1 flex items-center justify-center px-4 py-14 sm:px-8">
        <div className="absolute top-4 end-4">
          <LanguageMenuButton
            value={i18n.language}
            onChange={(code) => setUserLanguage(code)}
            buttonClassName="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-slate-600 hover:bg-slate-50"
          />
        </div>
        <div className="pointer-events-none absolute inset-0 aurora opacity-60" aria-hidden="true" />
        <div className={`auth-rise relative w-full rounded-3xl border border-white/70 bg-white/80 p-6 sm:p-8 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.25)] backdrop-blur-xl dark:border-white/10 dark:bg-white/5 ${wide ? 'max-w-[540px]' : 'max-w-[440px]'}`}>
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <span className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center shadow-sm">
              <GraduationCap className="w-5 h-5" />
            </span>
            <div className="leading-tight">
              <p className="font-bold text-slate-900">Code Cortex <span className="ms-1 text-xs font-semibold text-slate-400">CC-EMS</span></p>
              <p className="text-xs text-slate-500">{t('brand.product')}</p>
            </div>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}

/** Google "G" mark for sign-in buttons. */
export function GoogleMark({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}
