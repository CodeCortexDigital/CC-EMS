import { describe, expect, it } from 'vitest';
import { buildSections, sectionOpen } from './navSections';

describe('sidebar sections', () => {
  const items = [
    { id: 'fees', group: 'billing' }, { id: 'dashboard' }, { id: 'students', group: 'people' },
    { id: 'staff', group: 'people' }, { id: 'odd', group: 'nowhere' }, { id: 'settings', group: 'admin' },
  ];

  it('puts items under their headings in a fixed order, keeping their own order', () => {
    const s = buildSections(items);
    expect(s.map((x) => x.group)).toEqual(['', 'people', 'billing', 'admin']);
    expect(s[0].items.map((i) => i.id)).toEqual(['dashboard', 'odd']);
    expect(s[1].items.map((i) => i.id)).toEqual(['students', 'staff']);
  });

  it('opens only the heading with the current page until the person picks one', () => {
    const base = { picked: undefined, searching: false, collapsed: false, hasCurrentPage: false };
    expect(sectionOpen('people', base)).toBe(false);
    expect(sectionOpen('people', { ...base, hasCurrentPage: true })).toBe(true);
    expect(sectionOpen('', base)).toBe(true);
  });

  it('opening one heading closes the one before it, even the one with the current page', () => {
    const base = { searching: false, collapsed: false };
    expect(sectionOpen('billing', { ...base, picked: 'billing', hasCurrentPage: false })).toBe(true);
    expect(sectionOpen('people', { ...base, picked: 'billing', hasCurrentPage: true })).toBe(false);
    expect(sectionOpen('billing', { ...base, picked: null, hasCurrentPage: false })).toBe(false);
  });

  it('shows everything while searching or when the sidebar shows icons only', () => {
    const base = { picked: 'billing', hasCurrentPage: false };
    expect(sectionOpen('people', { ...base, searching: true, collapsed: false })).toBe(true);
    expect(sectionOpen('people', { ...base, searching: false, collapsed: true })).toBe(true);
  });
});
