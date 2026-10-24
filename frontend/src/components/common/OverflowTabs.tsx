// A row of underline tabs that always fits: what does not fit goes into a "More" menu instead of scrolling sideways.
// The current tab is always shown in the row, never hidden in the menu.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ComponentType } from 'react';
import { ChevronDown } from 'lucide-react';

export interface TabItem {
  id: string;
  label: string;
  icon?: ComponentType<{ className?: string }>;
}

interface Props {
  items: TabItem[];
  activeId: string;
  onSelect: (id: string) => void;
  ariaLabel?: string;
  /** Tabs are role="tab" inside a tablist (for in-page tabs) or plain buttons inside a nav (for page navigation). */
  role?: 'tab' | 'nav';
}

const MORE_WIDTH = 92;

/** How many tabs fit in `available` pixels, leaving room for the More button when some do not. */
export function fitCount(widths: number[], available: number): number {
  const total = widths.reduce((a, b) => a + b, 0);
  if (available <= 0 || total <= available) return widths.length;
  let used = MORE_WIDTH;
  let count = 0;
  for (const w of widths) {
    if (used + w > available) break;
    used += w;
    count += 1;
  }
  return Math.max(1, count);
}

export default function OverflowTabs({ items, activeId, onSelect, ariaLabel = 'Pages', role = 'nav' }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const measure = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState(items.length);
  const [open, setOpen] = useState(false);

  const recompute = useCallback(() => {
    const widths = Array.from(measure.current?.children ?? []).map((c) => (c as HTMLElement).offsetWidth);
    setFit(fitCount(widths, box.current?.clientWidth ?? 0));
  }, []);

  useLayoutEffect(() => { recompute(); }, [recompute, items]);
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined' || !box.current) return undefined;
    const ro = new ResizeObserver(recompute);
    ro.observe(box.current);
    return () => ro.disconnect();
  }, [recompute]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e: MouseEvent) => { if (!menuRef.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);

  // The row shows the first `fit` tabs; if the current tab would be in the menu, it takes the last place in the row.
  const activeIndex = items.findIndex((t) => t.id === activeId);
  let shown = items.slice(0, fit);
  if (fit < items.length && activeIndex >= fit) shown = [...items.slice(0, fit - 1), items[activeIndex]];
  const hidden = items.filter((t) => !shown.includes(t));

  const tab = (t: TabItem, hiddenForMeasure = false) => {
    const active = t.id === activeId;
    const Icon = t.icon;
    return (
      <button
        key={t.id}
        type="button"
        {...(hiddenForMeasure ? { tabIndex: -1, 'aria-hidden': true } : role === 'tab' ? { role: 'tab', 'aria-selected': active } : { 'aria-current': active ? ('page' as const) : undefined })}
        onClick={() => { setOpen(false); onSelect(t.id); }}
        className={`module-tab flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-[13px] border-b-2 transition-colors ${
          active ? 'module-tab-active font-semibold' : 'border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300 font-medium'
        }`}
      >
        {Icon && <Icon className={`w-4 h-4 ${active ? '' : 'text-slate-400'}`} />}
        {hiddenForMeasure ? <span className="measure-label" data-label={t.label} /> : t.label}
      </button>
    );
  };

  return (
    <div ref={box} className="relative min-w-0 flex-1">
      {/* Invisible copy of every tab, only to measure how wide each one is */}
      <div ref={measure} aria-hidden="true" className="pointer-events-none invisible absolute left-0 top-0 flex h-0 overflow-hidden gap-0.5 whitespace-nowrap">
        {items.map((t) => tab(t, true))}
      </div>

      <div role={role === 'tab' ? 'tablist' : undefined} aria-label={role === 'nav' ? undefined : ariaLabel} className="flex items-end gap-0.5 -mb-px">
        {role === 'nav' ? <nav aria-label={ariaLabel} className="flex items-end gap-0.5">{shown.map((t) => tab(t))}</nav> : shown.map((t) => tab(t))}
        {hidden.length > 0 && (
          <div ref={menuRef} className="relative shrink-0">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              className="module-tab flex items-center gap-1 whitespace-nowrap px-3 py-2.5 text-[13px] font-medium border-b-2 border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300"
            >
              More <span className="rounded-full bg-slate-100 px-1.5 text-[11px] leading-5 text-slate-600">{hidden.length}</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>
            {open && (
              <div role="menu" className="absolute right-0 top-full z-40 mt-1 min-w-[13rem] rounded-xl border border-slate-200 bg-white py-1.5 shadow-lg">
                {hidden.map((t) => {
                  const Icon = t.icon;
                  return (
                    <button key={t.id} role="menuitem" type="button" onClick={() => { setOpen(false); onSelect(t.id); }}
                      className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-50">
                      {Icon && <Icon className="w-4 h-4 text-slate-400" />}
                      {t.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
