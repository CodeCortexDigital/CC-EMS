// The top menu (staff roles). Text-only tabs along a dark bar, centred, on one line (what does not fit goes under "More").
// Pointing at a tab opens a wide panel of that area's pages; moving away closes it. Students and parents keep the compact side menu.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  BookOpen, Boxes, ChevronRight, GraduationCap, LayoutDashboard, MessageSquare, MoreHorizontal, PanelLeft, Settings, ShieldCheck, Star, TrendingUp,
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
  reports: 'Reports', admin: 'Admin', settings: 'Settings', account: 'Account',
};
const FULL: Record<string, string> = {
  home: 'Home', people: 'People', teaching: 'Teaching', academics: 'Academics', billing: 'Billing', communication: 'Communication', services: 'Campus services',
  reports: 'Reports', admin: 'Administration', settings: 'Settings', account: 'My account',
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
  admin: 'Security and privacy, importing data, integrations and the AI assistant.',
  settings: 'The school profile, theme, language, your account, plan and help.',
  account: 'Your privacy, help and account settings.',
};
const ICON: Record<string, typeof Users> = {
  home: LayoutDashboard, people: Users, teaching: GraduationCap, academics: BookOpen, billing: Wallet, communication: MessageSquare, services: Boxes,
  reports: TrendingUp, admin: ShieldCheck, settings: Settings, account: User,
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
  settings: { panel: '#eef4f1', tile: '#d9e8e1', accent: '#2f6f5e' },
  account: { panel: '#fdecf0', tile: '#fad4dd', accent: '#be123c' },
  favourites: { panel: '#fff6dc', tile: '#fdeab0', accent: '#b45309' },
  more: { panel: '#eef1f6', tile: '#dde3ec', accent: '#334155' },
};

// The panel opens and closes the moment the pointer arrives or leaves (the 12px strip under each tab covers the gap).
export const OPEN_DELAY_MS = 0;
export const CLOSE_DELAY_MS = 0;
const PANEL_FONT = "Raleway, 'Segoe UI', 'Yu Gothic UI', 'Hiragino Sans', Meiryo, system-ui, -apple-system, sans-serif";
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
      ? settingsSections.filter((s) => s.id !== 'security').map((s) => ({ key: `${id}:settings:${s.id}`, label: tl(s.label), href: s.path }))     // Settings: one entry per section (Security & privacy stays under Admin)
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
    setOpenId(id);
  }, []);
  const scheduleClose = () => {
    if (openTimer.current) window.clearTimeout(openTimer.current);
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    setOpenId(null);
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
    return `relative shrink-0 whitespace-nowrap rounded-none font-medium transition-colors ${active ? 'text-[color:var(--tab-accent)]' : 'text-white/90 hover:bg-white/10'}`;
  };
  const tabStyle = (id: string): React.CSSProperties => {
    const th = THEMES[id] || THEMES.more;
    const isOpen = openId === id;
    return { fontSize: 'clamp(13px, 1.03vw, 15px)', padding: '14px clamp(10px, 0.9vw, 18px)',
      ['--tab-accent' as any]: th.accent, background: isOpen ? th.accent : undefined, color: isOpen ? '#fff' : undefined };
  };

  const panelFor = (id: string) => {
    const th = THEMES[id] || THEMES.more;
    const base = { background: th.accent, color: '#fff', fontFamily: PANEL_FONT } as React.CSSProperties;
    if (id === 'more') {
      return (
        <div style={base} className="h-[280px] overflow-y-auto">
          <div className="mx-auto grid max-w-[1600px] gap-3 px-8 py-5 sm:grid-cols-2 xl:grid-cols-3">
            {hidden.map((m) => {
              const Icon = ICON[m.id] || Boxes;
              return (
                <div key={m.id} className="rounded-[var(--radius-xl,12px)] p-3" style={{ background: 'rgba(0,0,0,.16)' }}>
                  <p className="mb-2 flex items-center gap-2 text-sm font-bold text-white">
                    <Icon size={16} strokeWidth={1.5} />{FULL[m.id] || m.label}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {m.links.map((l) => (
                      <button key={l.key} onClick={() => go(l)} className="rounded-[var(--radius-lg,8px)] border border-white/30 px-2.5 py-1 text-xs text-white/80 hover:bg-white/15 hover:text-white">{l.label}</button>
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
      <div style={base} className="h-[280px]">
        <div className="mx-auto flex h-full max-w-[1600px] gap-6 px-8 py-5">
          <div className="flex w-60 shrink-0 flex-col items-center justify-center rounded-[var(--radius-xl,12px)] text-center" style={{ background: 'rgba(0,0,0,.22)' }}>
            <Icon size={56} strokeWidth={1.2} className="text-white" />
            <p className="mt-2 text-[1.35rem] font-extrabold uppercase tracking-wide text-white">{isFav ? 'Favourites' : FULL[id] || mod?.label}</p>
          </div>
          <div className="hidden w-72 shrink-0 flex-col justify-center rounded-[var(--radius-xl,12px)] p-5 lg:flex" style={{ background: 'rgba(0,0,0,.12)' }}>
            <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-white/70">About</p>
            <p className="mt-2 text-sm leading-relaxed text-white">{isFav ? 'Pages you starred. Click a star in any menu to add or remove one.' : mod?.description}</p>
            {first && !isFav && (
              <button onClick={() => go(first)} className="mt-4 w-fit rounded-[var(--radius-lg,8px)] border border-white px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-white hover:bg-white/10">
                Open
              </button>
            )}
          </div>
          <div className="min-w-0 flex-1 overflow-y-auto">
            {links.length === 0 ? <p className="p-4 text-sm text-white/80">No favourites yet. Click the star beside any page in the menu to keep it here.</p> : (
              <ul className="grid grid-cols-2 gap-x-6 gap-y-1 xl:grid-cols-3">
                {links.map((l) => {
                  const cur = isCurrent(l.href);
                  const starred = !!l.href && favourites.has(l.href);
                  return (
                    <li key={l.key} className={`group flex items-center gap-1 rounded-[var(--radius-lg,8px)] ${cur ? 'bg-white/15' : ''}`}>
                      <button onClick={() => go(l)} className={`flex min-w-0 flex-1 items-center gap-2 px-2.5 py-2 text-left text-base tracking-wider ${cur ? 'font-bold text-white' : 'text-white/80 hover:text-white'}`}>
                        <span aria-hidden="true" className="shrink-0 text-xs">&gt;</span><span className="truncate">{l.label}</span>
                      </button>
                      {l.href && (
                        <button onClick={() => star(l)} aria-label={starred ? `Remove ${l.label} from favourites` : `Add ${l.label} to favourites`} aria-pressed={starred}
                          className={`mr-1 rounded p-1 ${starred ? 'text-white' : 'text-white/60 hover:text-white'}`}>
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
    <div ref={root} className="relative hidden md:block" onMouseEnter={keepOpen} onMouseLeave={scheduleClose} data-testid="top-nav"
      onMouseOver={(e) => { if (openId && !(e.target as HTMLElement).closest?.('[data-menu-keep]')) setOpenId(null); }}>
      <nav aria-label="Main menu" className="px-4 py-0 sm:px-8" style={{ background: 'linear-gradient(to right, color-mix(in srgb, var(--app-accent-strong) 60%, #000), var(--app-accent-strong), var(--app-accent))', borderTop: '1px solid rgba(255,255,255,.12)' }}>
        <div className="flex items-center">
          {/* An empty block as wide as the right-hand buttons keeps the tabs in the middle of the whole bar */}
          <div style={{ width: rightWidth }} className="shrink-0" aria-hidden="true" />
          <div ref={tabsBox} className="relative flex min-w-0 flex-1 items-center justify-center" style={{ gap: 'clamp(2px, 0.95vw, 16px)' }}>
            {/* Invisible copy of every tab, only to measure widths */}
            <div ref={measure} aria-hidden="true" className="pointer-events-none invisible absolute left-0 top-0 flex h-0 overflow-hidden whitespace-nowrap" style={{ gap: 'clamp(2px, 0.95vw, 16px)' }}>
              {modules.map((m) => <span key={m.id} className="font-medium" style={{ fontSize: 'clamp(13px, 1.03vw, 15px)', padding: '14px clamp(10px, 0.9vw, 18px)' }}>{m.label}</span>)}
            </div>
            {shown.map((m) => {
              const current = activeModule === m.id;
              return (
                <div key={m.id} className="relative" data-menu-keep onMouseEnter={() => open(m.id)}>
                  <button type="button" aria-haspopup="true" aria-expanded={openId === m.id} aria-current={current ? 'page' : undefined}
                    onPointerDown={(e) => { pointer.current = e.pointerType === 'touch' ? 'touch' : 'mouse'; }} onClick={(e) => clickTab(m, e)}
                    className={tabClass(m.id, false)} style={current && openId !== m.id ? { ...tabStyle(m.id), background: '#fff', color: (THEMES[m.id] || THEMES.more).accent } : tabStyle(m.id)}>
                    {m.label}
                  </button>
                  {openId === m.id && th && <><span data-menu-keep aria-hidden="true" className="absolute inset-x-0 top-full h-3" /></>}
                </div>
              );
            })}
            {hasMore && (
              <div className="relative" data-menu-keep onMouseEnter={() => open('more')}>
                <button type="button" aria-haspopup="true" aria-expanded={openId === 'more'} className={tabClass('more', false)} style={tabStyle('more')}>
                  <span className="inline-flex items-center gap-1">More <MoreHorizontal size={14} /></span>
                </button>
                {openId === 'more' && th && <><span data-menu-keep aria-hidden="true" className="absolute inset-x-0 top-full h-3" /></>}
              </div>
            )}
          </div>
          <div ref={rightBox} className="flex shrink-0 items-center gap-1 text-white">
            <div className="relative" data-menu-keep onMouseEnter={() => open('favourites')}>
              <button type="button" aria-label="Favourites" aria-haspopup="true" aria-expanded={openId === 'favourites'} className="inline-flex items-center gap-1.5 rounded-none px-3 py-[14px] text-sm hover:bg-white/10"
                style={openId === 'favourites' ? tabStyle('favourites') : undefined}>
                <Star size={16} /><span className="hidden 2xl:inline">Favourites</span>
              </button>
              {openId === 'favourites' && th && <><span data-menu-keep aria-hidden="true" className="absolute inset-x-0 top-full h-3" /></>}
            </div>
            <button type="button" onClick={() => setNavLayout(navLayout === 'top' ? 'side' : 'top')} aria-label="Switch to the side menu" title="Switch to the side menu"
              className="inline-flex items-center gap-1.5 rounded-none px-3 py-[14px] text-sm hover:bg-white/10">
              <PanelLeft size={16} /><span className="hidden 2xl:inline">Sidebar</span>
            </button>
          </div>
        </div>
      </nav>
      {openId && (
        <div role="region" data-menu-keep aria-label={`${openId} pages`} className="absolute inset-x-0 top-full z-50 border-b border-black/5" style={{ boxShadow: '0 24px 40px -24px rgba(15,23,42,.35)' }}>
          {panelFor(openId)}
        </div>
      )}
    </div>
  );
}
