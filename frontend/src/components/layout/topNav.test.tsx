// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ logout: vi.fn(), user: {}, role: 'admin' }) }));
vi.mock('@/utils/region', () => ({ useRegion: () => ({ label: (s: string) => s }) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (_k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? _k }) }));
vi.mock('./useNavItems', () => ({
  useNavItems: () => [
    { id: 'dashboard', label: 'Dashboard', href: '/dashboard', icon: null },
    { id: 'students', label: 'Students', href: '/education/students', group: 'people', icon: null },
    { id: 'admissions', label: 'Admissions', href: '/education/admissions', group: 'people', icon: null },
    { id: 'timetable', label: 'Timetable', href: '/education/timetable', group: 'academics', icon: null },
    { id: 'settings', label: 'Settings', href: '/settings', group: 'admin', icon: null },
  ],
}));

import { toast } from 'sonner';
import { useFavourites, MAX_FAVOURITES } from '@/store/favouritesStore';
import TopNav, { CLOSE_DELAY_MS, OPEN_DELAY_MS, tabsThatFit } from './TopNav';

function Where() { return <p data-testid="where">{useLocation().pathname}</p>; }
const renderNav = (path = '/dashboard') => render(<MemoryRouter initialEntries={[path]}><TopNav /><Where /></MemoryRouter>);
const tab = (name: string) => within(screen.getByRole('navigation', { name: 'Main menu' })).getByRole('button', { name });
const hover = (name: string) => fireEvent.mouseEnter(tab(name).parentElement as HTMLElement);
const wait = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); useFavourites.setState({ items: [] }); vi.clearAllMocks(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('tabsThatFit', () => {
  it('shows everything when it fits and leaves room for More when it does not', () => {
    expect(tabsThatFit([100, 100, 100], 400)).toBe(3);
    expect(tabsThatFit([100, 100, 100], 0)).toBe(3);                    // width not known yet
    expect(tabsThatFit([100, 100, 100, 100, 100], 300)).toBe(2);        // 64 for More + 2 x 100
    expect(tabsThatFit([500, 500], 300)).toBe(1);                       // never fewer than one
  });
});

describe('Top menu', () => {
  it('lists the areas as text tabs and marks the one you are in', () => {
    renderNav('/education/students');
    for (const name of ['Home', 'People', 'Academics', 'Admin']) expect(tab(name)).toBeTruthy();
    expect(tab('People').getAttribute('aria-current')).toBe('page');
    expect(tab('Academics').getAttribute('aria-current')).toBeNull();
  });

  it('opens a panel after a short delay when the pointer is on a tab, and closes it a moment after it leaves', () => {
    renderNav();
    hover('People');
    expect(screen.queryByRole('region')).toBeNull();
    wait(OPEN_DELAY_MS + 5);
    const panel = screen.getByRole('region');
    expect(within(panel).getByText('Students')).toBeTruthy();
    expect(within(panel).getByText('Admissions')).toBeTruthy();
    expect(tab('People').getAttribute('aria-expanded')).toBe('true');
    fireEvent.mouseLeave(screen.getByTestId('top-nav'));
    wait(CLOSE_DELAY_MS - 20);
    expect(screen.queryByRole('region')).not.toBeNull();                // still open: it waits so crossing a gap does not close it
    wait(40);
    expect(screen.queryByRole('region')).toBeNull();
  });

  it('moving to another tab switches the panel at once, and coming back to the panel keeps it open', () => {
    renderNav();
    hover('People'); wait(OPEN_DELAY_MS + 5);
    hover('Academics');
    expect(within(screen.getByRole('region')).getByText('Timetable')).toBeTruthy();   // no delay when one is already open
    fireEvent.mouseLeave(screen.getByTestId('top-nav'));
    wait(100);
    fireEvent.mouseEnter(screen.getByTestId('top-nav'));                 // back onto the bar or panel
    wait(500);
    expect(screen.queryByRole('region')).not.toBeNull();
  });

  it('Escape closes the panel, and going to a page closes it too', () => {
    renderNav();
    hover('People'); wait(OPEN_DELAY_MS + 5);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('region')).toBeNull();
    hover('People'); wait(OPEN_DELAY_MS + 5);
    fireEvent.click(within(screen.getByRole('region')).getByText('Admissions'));
    expect(screen.getByTestId('where').textContent).toBe('/education/admissions');
    expect(screen.queryByRole('region')).toBeNull();
  });

  it('clicking a tab goes to the first page of that area', () => {
    renderNav();
    fireEvent.click(tab('Academics'));
    expect(screen.getByTestId('where').textContent).toBe('/education/timetable');
  });

  it('Settings lists every settings section instead of one entry', () => {
    renderNav();
    hover('Admin'); wait(OPEN_DELAY_MS + 5);
    const panel = screen.getByRole('region');
    for (const name of ['Profile', 'Theme', 'Language & currency', 'Account', 'Plan & billing', 'Security & privacy']) expect(within(panel).getByText(name)).toBeTruthy();
  });

  it('stars a page, lists it under Favourites, and refuses a ninth with a clear message', () => {
    renderNav();
    hover('People'); wait(OPEN_DELAY_MS + 5);
    fireEvent.click(screen.getByLabelText('Add Students to favourites'));
    expect(useFavourites.getState().items.map((f) => f.href)).toEqual(['/education/students']);
    hover('Favourites'); wait(5);
    expect(within(screen.getByRole('region')).getByText('Students')).toBeTruthy();
    for (let i = 0; i < MAX_FAVOURITES; i++) useFavourites.getState().toggle({ href: `/x${i}`, label: `X${i}` });
    expect(useFavourites.getState().items).toHaveLength(MAX_FAVOURITES);
    hover('People'); wait(5);
    fireEvent.click(screen.getByLabelText('Add Admissions to favourites'));
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('favourites are full'));
    expect(useFavourites.getState().items).toHaveLength(MAX_FAVOURITES);
  });

  it('switches to the side menu', async () => {
    const { useUIStore } = await import('@/store/uiStore');
    expect(useUIStore.getState().navLayout).toBe('side');
    useUIStore.getState().setNavLayout('top');
    renderNav();
    fireEvent.click(screen.getByLabelText('Switch to the side menu'));
    expect(useUIStore.getState().navLayout).toBe('side');
  });
});
