// The top menu (staff roles). Text-only tabs along a dark bar, centred, on one line (what does not fit goes under "More").
// Pointing at a tab opens a wide panel of that area's pages; moving away closes it. Students and parents keep the compact side menu.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  BookOpen, Boxes, ChevronRight, GraduationCap, LayoutDashboard, MessageSquare, MoreHorizontal, PanelLeft, Settings, Star, TrendingUp,
  User, Users, Wallet,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { useRegion } from '@/utils/region';
import { useUIStore } from '@/store/uiStore';
import { FAVOURITES_FULL_MESSAGE, useFavourites } from '@/store/favouritesStore';
import { buildSections } from './navSections';
import { useNavItems } from './useNavItems';
import { menuItems as settingsSections } from '@/pages/settings/components/SettingsSidebar';

export interface NavLinkItem { key: string; label: string; href?: string; onClick?: () => void }
export interface NavModule { id: string; label: string; description: string; links: NavLinkItem[] }

/** Short names for the bar. Page titles keep the full name. */
const SHORT: Record<string, string> = {
  home: 'Home', people: 'People', teaching: 'Teaching', academics: 'Academics', billing: 'Billing', communication: 'Comms', services: 'Services',
  reports: 'Reports', admin: 'Admin', account: 'Account',
};
const FULL: Record<string, string> = {
  home: 'Home', people: 'People', teaching: 'Teaching', academics: 'Academics', billing: 'Billing', communication: 'Communication', services: 'Campus services',
  reports: 'Reports', admin: 'Administration', account: 'My account',
};
const ABOUT: Record<string, string> = {
  home: 'Your dashboard, the daily brief and what needs your approval.',
  people: 'Students, staff, admissions and the offices that look after them.',
  teaching: 'Your classes, reports, cover and the tools for teaching.',
  academics: 'Timetable, attendance, gradebook, exams and certificates.',
  billing: 'Fees, salaries and the school accounts.',
  communication: 'Messages, announcements, the calendar and meetings.',
  services: 'Library, transport, inventory and the cafeteria.',
  reports: 'Insights on enrolment, attendance, finance and results.',
  admin: 'Security, imports, integrations and the school settings.',
  account: 'Your privacy, help and account settings.',
};
const ICON: Record<string, typeof Users> = {
  home: LayoutDashboard, people: Users, teaching: GraduationCap, academics: BookOpen, billing: Wallet, communication: MessageSquare, services: Boxes,
  reports: TrendingUp, admin: Settings, account: User,
};
/** Very light panel, a slightly deeper tile, and an accent strong enough for 15px text. */
const THEMES: Record<string, { panel: string; tile: string; accent: string }> = {
  home: { panel: '#e9f6f3', tile: '#cdeae4', accent: '#0f766e' },
  people: { panel: '#f1ebfc', tile: '#e0d5f8', accent: '#6d28d9' },
  teaching: { panel: '#e9f0fd', tile: '#d3e1fb', accent: '#1d4ed8' },
  academics: { panel: '#edeffd', tile: '#dadefa', accent: '#4338ca' },
  billing: { panel: '#e6f6ee', tile: '#cbeddb', accent: '#047857' },
  communication: { panel: '#fdf0e6', tile: '#fadfc9', accent: '#c2410c' },
  services: { panel: '#e4f5f9', tile: '#c8e8f0', accent: '#0e7490' },
  reports: { panel: '#e5f2fb', tile: '#c9e3f5', accent: '#0369a1' },
  admin: { panel: '#eff2f6', tile: '#dde3eb', accent: '#475569' },
  account: { panel: '#fdecf0', tile: '#fad4dd', accent: '#be123c' },
  favourites: { panel: '#fff6dc', tile: '#fdeab0', accent: '#b45309' },
  more: { panel: '#eef1f6', tile: '#dde3ec', accent: '#334155' },
};

export const OPEN_DELAY_MS = 70;
export const CLOSE_DELAY_MS = 220;
const MORE_WIDTH = 64;

/** How many tabs fit in `available` px (leaving room for More when some do not). Pure, so it can be tested. */
export function tabsThatFit(widths: number[], available: number): number {
  const total = widths.reduce((a, b) => a + b, 0);
  if (available <= 0 || total <= available) return widths.length;
  let used = MORE_WIDTH;
  let n = 0;
  for (const w of widths) { if (used + w > available) break; used += w; n += 1; }
  return Math.max(1, n);
}

const pathOf = (href?: string) => (href || '').split('?')[0];
/** The same page is listed once, even when two menu entries lead to it. */
const dedupe = (links: NavLinkItem[]) => links.filter((l, i) => !l.href || links.findIndex((o) => o.href === l.href) === i);

/** The areas of the menu for the signed-in person, from the same data as the side menu. */
export function useNavModules(): NavModule[] {
  const items = useNavItems();
  const { t } = useTranslation();
  const { label: regionLabel } = useRegion();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const tl = (label: string) => regionLabel(t(`nav.${label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')}`, { defaultValue: label }));
  return useMemo(() => buildSections(items).map((sec) => {
    const id = sec.group || 'home';
    const links: NavLinkItem[] = dedupe(sec.items.flatMap((item): NavLinkItem[] => item.id === 'settings' && !item.subItems
      ? settingsSections.map((s) => ({ key: `${id}:settings:${s.id}`, label: tl(s.label), href: s.path }))     // Settings: one entry per section
      : item.subItems
      ? item.subItems.filter((s) => !s.isDivider).map((s) => (s.isLogout
        ? { key: `${id}:logout`, label: 'Log out', onClick: () => { logout(); navigate('/login'); } }
        : { key: `${id}:${item.id}:${s.href}`, label: tl(s.label), href: s.href }))
      : [{ key: `${id}:${item.id}`, label: tl(item.label), href: item.href }]));
    return { id, label: SHORT[id] || id, description: ABOUT[id] || `Everything in ${FULL[id] || id}.`, links };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }).filter((m) => m.links.length > 0), [items, t]);
}

export default function TopNav() {
  const modules = useNavModules();
  const location = useLocation();
  const navigate = useNavigate();
  const { navLayout, setNavLayout } = useUIStore();
  const favourites = useFavourites();

  const [openId, setOpenId] = useState<string | null>(null);
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const tabsBox = useRef<HTMLDivElement>(null);
  const measure = useRef<HTMLDivElement>(null);
  const rightBox = useRef<HTMLDivElement>(null);
  const pointer = useRef<'mouse' | 'touch'>('mouse');
  const [fit, setFit] = useState(modules.length);
  const [rightWidth, setRightWidth] = useState(0);

  const clear = () => { if (openTimer.current) window.clearTimeout(openTimer.current); if (closeTimer.current) window.clearTimeout(closeTimer.current); };
  useEffect(() => clear, []);
  const open = useCallback((id: string) => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    if (openTimer.current) window.clearTimeout(openTimer.current);
    if (openId !== null) setOpenId(id);                                   // another panel is open: switch at once
    else openTimer.current = window.setTimeout(() => setOpenId(id), OPEN_DELAY_MS);
  }, [openId]);
  const scheduleClose = () => {
    if (openTimer.current) window.clearTimeout(openTimer.current);
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpenId(null), CLOSE_DELAY_MS);
  };
  const keepOpen = () => { if (closeTimer.current) window.clearTimeout(closeTimer.current); };

  useEffect(() => { clear(); setOpenId(null); }, [location.pathname, location.search]);          // going somewhere closes the panel
  useEffect(() => {
    if (!openId) return undefined;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpenId(null); };
    const outside = (e: MouseEvent | TouchEvent) => { if (!root.current?.contains(e.target as Node)) setOpenId(null); };
    document.addEventListener('keydown', esc);
    document.addEventListener('mousedown', outside);
    document.addEventListener('touchstart', outside);
    return () => { document.removeEventListener('keydown', esc); document.removeEventListener('mousedown', outside); document.removeEventListener('touchstart', outside); };
  }, [openId]);

  // Keep the tabs centred and on one line: measure every tab, show what fits, put the rest under More.
  const recompute = useCallback(() => {
    const widths = Array.from(measure.current?.children ?? []).map((c) => (c as HTMLElement).offsetWidth);
    setFit(tabsThatFit(widths, tabsBox.current?.clientWidth ?? 0));
    setRightWidth(rightBox.current?.offsetWidth ?? 0);
  }, []);
  useLayoutEffect(() => { recompute(); }, [recompute, modules]);
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(recompute);
    if (root.current) ro.observe(root.current);
    return () => ro.disconnect();
  }, [recompute]);

  const isCurrent = (href?: string) => {
    const p = pathOf(href);
    if (!p || p === '#') return false;
    if (p === '/dashboard' || p === '/teacher') return location.pathname === p;
    return location.pathname === p || location.pathname.startsWith(p.endsWith('/') ? p : `${p}/`);
  };
  const activeModule = modules.find((m) => m.links.some((l) => isCurrent(l.href)))?.id;
  const shown = modules.slice(0, fit);
  const hidden = modules.slice(fit);
  const hasMore = hidden.length > 0;
  const moduleHasPage = (m: NavModule) => m.links.find((l) => l.href);

  const go = (l: NavLinkItem) => { setOpenId(null); if (l.onClick) l.onClick(); else if (l.href) navigate(l.href); };
  const star = (l: NavLinkItem) => {
    if (!l.href) return;
    if (!favourites.toggle({ href: l.href, label: l.label })) toast.error(FAVOURITES_FULL_MESSAGE);
  };
  const clickTab = (m: NavModule, e: React.MouseEvent) => {
    if (pointer.current === 'touch' && openId !== m.id) { e.preventDefault(); setOpenId(m.id); return; }    // first tap opens, second goes
    const first = moduleHasPage(m);
    if (first) go(first);
  };

  const tabClass = (id: string, current: boolean) => {
    const active = openId === id || current;
    return `relative shrink-0 whitespace-nowrap rounded-[var(--radius-2xl,16px)] font-medium transition-colors ${active ? 'text-[color:var(--tab-accent)]' : 'text-white/90 hover:bg-white/10'}`;
  };
  const tabStyle = (id: string): React.CSSProperties => {
    const th = THEMES[id] || THEMES.more;
    const isOpen = openId === id;
    return { fontSize: 'clamp(13px, 1.03vw, 15px)', padding: '8px clamp(8px, 0.78vw, 14px)',
      ['--tab-accent' as any]: th.accent, background: isOpen ? th.panel : undefined, color: isOpen ? th.accent : undefined };
  };

  const panelFor = (id: string) => {
    const th = THEMES[id] || THEMES.more;
    const base = { background: th.panel, ['--accent' as any]: th.accent } as React.CSSProperties;
    if (id === 'more') {
      return (
        <div style={base} className="h-[17.5rem] overflow-y-auto">
          <div className="mx-auto grid max-w-[1600px] gap-3 px-8 py-5 sm:grid-cols-2 xl:grid-cols-3">
            {hidden.map((m) => {
              const t2 = THEMES[m.id] || THEMES.more; const Icon = ICON[m.id] || Boxes;
              return (
                <div key={m.id} className="rounded-[var(--radius-xl,12px)] bg-white p-3 shadow-sm">
                  <p className="mb-2 flex items-center gap-2 text-sm font-bold" style={{ color: t2.accent }}>
                    <span className="flex h-7 w-7 items-center justify-center rounded-full" style={{ background: t2.tile }}><Icon size={15} /></span>{FULL[m.id] || m.label}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {m.links.map((l) => (
                      <button key={l.key} onClick={() => go(l)} className="rounded-[var(--radius-lg,8px)] border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:text-white" style={{ ['--hover' as any]: t2.accent }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = t2.accent; }} onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}>{l.label}</button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }
    const isFav = id === 'favourites';
    const links: NavLinkItem[] = isFav ? favourites.items.map((f) => ({ key: `fav:${f.href}`, label: f.label, href: f.href })) : (modules.find((m) => m.id === id)?.links || []);
    const mod = modules.find((m) => m.id === id);
    const Icon = isFav ? Star : ICON[id] || Boxes;
    const first = links.find((l) => l.href);
    return (
      <div style={base} className="h-[17.5rem]">
        <div className="mx-auto flex h-full max-w-[1600px] gap-6 px-8 py-5">
          <div className="flex w-60 shrink-0 flex-col items-center justify-center rounded-[var(--radius-xl,12px)] text-center" style={{ background: th.tile }}>
            <Icon size={56} strokeWidth={1.2} style={{ color: th.accent }} />
            <p className="mt-2 text-[1.35rem] font-extrabold uppercase tracking-wide" style={{ color: th.accent }}>{isFav ? 'Favourites' : FULL[id] || mod?.label}</p>
          </div>
          <div className="hidden w-72 shrink-0 flex-col justify-center rounded-[var(--radius-xl,12px)] p-5 lg:flex" style={{ background: 'rgba(255,255,255,.45)' }}>
            <p className="font-mono text-[10px] uppercase tracking-[0.3em]" style={{ color: th.accent }}>About</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{isFav ? 'Pages you starred. Click a star in any menu to add or remove one.' : mod?.description}</p>
            {first && !isFav && (
              <button onClick={() => go(first)} className="mt-4 w-fit rounded-[var(--radius-lg,8px)] border px-3 py-1.5 text-xs font-bold uppercase tracking-wide" style={{ borderColor: th.accent, color: th.accent }}>
                Open {(FULL[id] || mod?.label || '').toLowerCase()}
              </button>
            )}
          </div>
          <div className="min-w-0 flex-1 overflow-y-auto">
            {links.length === 0 ? <p className="p-4 text-sm text-slate-500">No favourites yet. Click the star beside any page in the menu to keep it here.</p> : (
              <ul className="grid grid-cols-2 gap-x-6 gap-y-1 xl:grid-cols-3">
                {links.map((l) => {
                  const cur = isCurrent(l.href);
                  const starred = !!l.href && favourites.has(l.href);
                  return (
                    <li key={l.key} className={`group flex items-center gap-1 rounded-[var(--radius-lg,8px)] ${cur ? 'bg-white shadow-sm' : 'hover:bg-white/60'}`}>
                      <button onClick={() => go(l)} className="flex min-w-0 flex-1 items-center gap-1.5 px-2.5 py-2 text-left text-[15px]" style={{ color: cur ? th.accent : '#334155', fontWeight: cur ? 600 : 400 }}>
                        <ChevronRight size={14} style={{ color: th.accent }} className="shrink-0" /><span className="truncate">{l.label}</span>
                      </button>
                      {l.href && (
                        <button onClick={() => star(l)} aria-label={starred ? `Remove ${l.label} from favourites` : `Add ${l.label} to favourites`} aria-pressed={starred}
                          className="mr-1 rounded p-1" style={{ color: starred ? '#d97706' : '#94a3b8' }}>
                          <Star size={15} fill={starred ? 'currentColor' : 'none'} />
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    );
  };

  const th = openId ? THEMES[openId] || THEMES.more : null;
  return (
    <div ref={root} className="relative hidden md:block" onMouseEnter={keepOpen} onMouseLeave={scheduleClose} data-testid="top-nav">
      <nav aria-label="Main menu" className="px-4 py-2 sm:px-8" style={{ background: 'linear-gradient(to right, color-mix(in srgb, var(--app-accent-strong) 60%, #000), var(--app-accent-strong), var(--app-accent))', borderTop: '1px solid rgba(255,255,255,.12)' }}>
        <div className="flex items-center">
          {/* An empty block as wide as the right-hand buttons keeps the tabs in the middle of the whole bar */}
          <div style={{ width: rightWidth }} className="shrink-0" aria-hidden="true" />
          <div ref={tabsBox} className="relative flex min-w-0 flex-1 items-center justify-center" style={{ gap: 'clamp(2px, 0.95vw, 16px)' }}>
            {/* Invisible copy of every tab, only to measure widths */}
            <div ref={measure} aria-hidden="true" className="pointer-events-none invisible absolute left-0 top-0 flex h-0 overflow-hidden whitespace-nowrap" style={{ gap: 'clamp(2px, 0.95vw, 16px)' }}>
              {modules.map((m) => <span key={m.id} className="font-medium" style={{ fontSize: 'clamp(13px, 1.03vw, 15px)', padding: '8px clamp(8px, 0.78vw, 14px)' }}>{m.label}</span>)}
            </div>
            {shown.map((m) => {
              const current = activeModule === m.id;
              return (
                <div key={m.id} className="relative" onMouseEnter={() => open(m.id)}>
                  <button type="button" aria-haspopup="true" aria-expanded={openId === m.id} aria-current={current ? 'page' : undefined}
                    onPointerDown={(e) => { pointer.current = e.pointerType === 'touch' ? 'touch' : 'mouse'; }} onClick={(e) => clickTab(m, e)}
                    className={tabClass(m.id, false)} style={current && openId !== m.id ? { ...tabStyle(m.id), background: '#fff', color: (THEMES[m.id] || THEMES.more).accent } : tabStyle(m.id)}>
                    {m.label}
                  </button>
                  {openId === m.id && th && <span aria-hidden="true" className="absolute left-1/2 top-full -translate-x-1/2 border-x-8 border-t-8 border-x-transparent" style={{ borderTopColor: th.panel }} />}
                </div>
              );
            })}
            {hasMore && (
              <div className="relative" onMouseEnter={() => open('more')}>
                <button type="button" aria-haspopup="true" aria-expanded={openId === 'more'} className={tabClass('more', false)} style={tabStyle('more')}>
                  <span className="inline-flex items-center gap-1">More <MoreHorizontal size={14} /></span>
                </button>
                {openId === 'more' && th && <span aria-hidden="true" className="absolute left-1/2 top-full -translate-x-1/2 border-x-8 border-t-8 border-x-transparent" style={{ borderTopColor: th.panel }} />}
              </div>
            )}
          </div>
          <div ref={rightBox} className="flex shrink-0 items-center gap-1 text-white">
            <div className="relative" onMouseEnter={() => open('favourites')}>
              <button type="button" aria-label="Favourites" aria-haspopup="true" aria-expanded={openId === 'favourites'} className="inline-flex items-center gap-1.5 rounded-[var(--radius-lg,8px)] px-2.5 py-2 text-sm hover:bg-white/10"
                style={openId === 'favourites' ? tabStyle('favourites') : undefined}>
                <Star size={16} /><span className="hidden 2xl:inline">Favourites</span>
              </button>
              {openId === 'favourites' && th && <span aria-hidden="true" className="absolute left-1/2 top-full -translate-x-1/2 border-x-8 border-t-8 border-x-transparent" style={{ borderTopColor: th.panel }} />}
            </div>
            <button type="button" onClick={() => setNavLayout(navLayout === 'top' ? 'side' : 'top')} aria-label="Switch to the side menu" title="Switch to the side menu"
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-lg,8px)] px-2.5 py-2 text-sm hover:bg-white/10">
              <PanelLeft size={16} /><span className="hidden 2xl:inline">Sidebar</span>
            </button>
          </div>
        </div>
      </nav>
      {openId && (
        <div role="region" aria-label={`${openId} pages`} className="absolute inset-x-0 top-full z-50 border-b border-black/5" style={{ boxShadow: '0 24px 40px -24px rgba(15,23,42,.35)' }}>
          {panelFor(openId)}
        </div>
      )}
    </div>
  );
}
