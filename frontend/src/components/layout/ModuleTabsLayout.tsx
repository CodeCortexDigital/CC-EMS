import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import OverflowTabs from '@/components/common/OverflowTabs';

export interface ModuleTab {
  id: string;
  path: string; // full path used for navigation AND active matching (may include ?query)
  label: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  // Legacy per-tab colours; tabs now all use the theme accent.
  dark?: string;
  light?: string;
  rgb?: string;
  roles?: string[]; // when set, tab is only shown to these roles
}

interface Props {
  tabs: ModuleTab[];
  scopeClass: string;
  children?: React.ReactNode;
  /** Keep a tab highlighted on its sub-pages (e.g. /students/edit/5 under "Students"). */
  matchNested?: boolean;
}

const isActive = (t: ModuleTab, pathname: string, search: string, nestedBase?: string) => {
  const [path, query] = t.path.split('?');
  if (nestedBase !== undefined && !query) {
    return path === nestedBase ? pathname === path : pathname.startsWith(path);
  }
  if (pathname !== path) return false;
  const curParams = new URLSearchParams(search);
  if (!query) {
    // A query-less tab is only active when no query params are present
    return [...curParams.keys()].length === 0;
  }
  const tParams = new URLSearchParams(query);
  for (const [k, v] of tParams.entries()) {
    if (curParams.get(k) !== v) return false;
  }
  return true;
};

import { useRegion } from '@/utils/region';

export default function ModuleTabsLayout({ tabs, scopeClass, children, matchNested }: Props) {
  const { label: regionLabel } = useRegion();
  const location = useLocation();
  const navigate = useNavigate();
  const { role } = useAuth();

  const visibleTabs = tabs.filter((t) => !t.roles || (role && t.roles.includes(role)));
  const nestedBase = matchNested ? tabs[0]?.path.split('?')[0] : undefined;
  const activeTab = visibleTabs.find((t) => isActive(t, location.pathname, location.search, nestedBase)) || visibleTabs[0] || tabs[0];

  return (
    <div className={`${scopeClass} min-h-full`}>
      {/* Section header: the page name, then the section's pages as underline tabs (any that do not fit go under a More menu) */}
      <div className="module-header bg-white border-b border-slate-200 px-3 sm:px-5 sticky top-0 z-30 flex items-end gap-4">
        <h2 className="shrink-0 self-center pr-4 border-r border-slate-200 text-base font-semibold tracking-tight text-slate-900 hidden md:block">{regionLabel(activeTab.label)}</h2>
        <h2 className="sr-only md:hidden">{regionLabel(activeTab.label)}</h2>
        <OverflowTabs
          ariaLabel="Section pages"
          items={visibleTabs.map((t) => ({ id: t.id, label: regionLabel(t.label), icon: t.icon }))}
          activeId={visibleTabs.find((t) => isActive(t, location.pathname, location.search, nestedBase))?.id ?? ''}
          onSelect={(id) => { const t = visibleTabs.find((x) => x.id === id); if (t) navigate(t.path); }}
        />
      </div>

      {/* Content */}
      <div className="p-3 sm:p-4 min-h-full bg-slate-50">
        {children ?? <Outlet />}
      </div>
    </div>
  );
}
