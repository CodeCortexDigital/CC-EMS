// Sidebar sections (Phase 22): which items go under which heading, and whether a heading is open.

// Sections in the order they appear; each role only uses some of them. '' is the top (no heading).
export const GROUP_ORDER = ['', 'people', 'teaching', 'family', 'learning', 'academics', 'billing', 'communication', 'services', 'reports', 'admin', 'settings', 'account'];

export function buildSections<T extends { group?: string }>(items: T[]): { group: string; items: T[] }[] {
  const known = new Set(GROUP_ORDER);
  return GROUP_ORDER
    // An item with an unknown section still shows, at the top, rather than disappearing.
    .map((g) => ({ group: g, items: items.filter((i) => (known.has(i.group || '') ? i.group || '' : '') === g) }))
    .filter((s) => s.items.length > 0);
}

// One heading is open at a time. `picked` is what the person last chose: a heading, null (they closed it), or undefined
// (nothing chosen yet, so the heading holding the current page is the one that is open).
export function sectionOpen(group: string, o: { picked: string | null | undefined; searching: boolean; collapsed: boolean; hasCurrentPage: boolean }): boolean {
  if (!group || o.searching || o.collapsed) return true;
  return o.picked === undefined ? o.hasCurrentPage : o.picked === group;
}
