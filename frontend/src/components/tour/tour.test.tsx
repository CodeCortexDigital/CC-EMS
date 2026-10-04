// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const auth = vi.hoisted(() => ({ role: 'admin' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: auth.role }) }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

import api from '@/services/api';
import { ALL_TOURS, tourFor } from '@/config/tourSteps';
import { needsTour, startTour } from '@/services/tour.service';
import GuidedTour from './GuidedTour';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

describe('tour steps', () => {
  it('every kind of person who can sign in has a tour, and every step reads properly', () => {
    for (const role of ['admin', 'teacher', 'parent', 'student', 'front_desk', 'nurse', 'counsellor', 'staff', 'manager', 'hr']) {
      const tour = tourFor(role)!;
      expect(tour, role).toBeTruthy();
      expect(tour.steps.length).toBeGreaterThanOrEqual(3);
      for (const s of tour.steps) {
        expect(s.title.length).toBeGreaterThan(3);
        expect(s.body.length).toBeGreaterThan(20);
        if (s.href) { expect(s.href.startsWith('/')).toBe(true); expect(s.linkLabel).toBeTruthy(); }
      }
    }
    expect(tourFor('user')).toBeNull();
    expect(tourFor(null)).toBeNull();
  });

  it('never points a person at a page their role cannot open', () => {
    const adminOnly = ['/education/import', '/education/fees', '/education/forms', '/education/admissions', '/education/students', '/education/timetable', '/settings/integrations', '/dashboard'];
    for (const role of ['teacher', 'parent', 'student', 'front_desk', 'nurse', 'counsellor', 'staff']) {
      for (const s of ALL_TOURS[role].steps) {
        expect(adminOnly.some((p) => s.href?.startsWith(p)), `${role}: ${s.href}`).toBe(false);
      }
    }
    for (const role of ['parent', 'student']) {
      for (const s of ALL_TOURS[role].steps) expect(s.href?.startsWith('/education/'), `${role}: ${s.href}`).toBeFalsy();
    }
    expect(ALL_TOURS.parent.steps.some((s) => s.href === '/parent/forms')).toBe(true);
  });

  it('shows a tour again only when its version has moved on', () => {
    expect(needsTour({}, 'admin', 1)).toBe(true);
    expect(needsTour({ admin: { version: 1, status: 'completed' } }, 'admin', 1)).toBe(false);
    expect(needsTour({ admin: { version: 1, status: 'skipped' } }, 'admin', 2)).toBe(true);
  });
});

function renderTour() {
  return render(<MemoryRouter><GuidedTour /></MemoryRouter>);
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); auth.role = 'admin'; post.mockResolvedValue({ data: { tours: {} } }); });

describe('GuidedTour', () => {
  it('opens for someone who has never seen it, and remembers when they finish', async () => {
    get.mockResolvedValue({ data: { tours: {} } });
    renderTour();
    expect(await screen.findByRole('dialog', { name: 'Guided tour' })).toBeTruthy();
    expect(screen.getByText(/Step 1 of/)).toBeTruthy();
    const total = ALL_TOURS.admin.steps.length;
    for (let i = 1; i < total; i++) fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    fireEvent.click(screen.getByRole('button', { name: 'Finish' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/tour/progress/', { tour: 'admin', version: ALL_TOURS.admin.version, status: 'completed' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('can be skipped, and the skip is remembered', async () => {
    get.mockResolvedValue({ data: { tours: {} } });
    renderTour();
    fireEvent.click(await screen.findByRole('button', { name: 'Skip the tour' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/tour/progress/', { tour: 'admin', version: ALL_TOURS.admin.version, status: 'skipped' }));
  });

  it('stays closed for someone who has already seen it, until they ask to replay it', async () => {
    get.mockResolvedValue({ data: { tours: { admin: { version: ALL_TOURS.admin.version, status: 'completed' } } } });
    renderTour();
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(screen.queryByRole('dialog')).toBeNull();
    startTour();
    expect(await screen.findByRole('dialog', { name: 'Guided tour' })).toBeTruthy();
  });

  it('does not nag when it cannot tell whether the tour was seen', async () => {
    get.mockRejectedValue(new Error('offline'));
    renderTour();
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('a role without a tour shows nothing and asks nothing', () => {
    auth.role = 'user';
    renderTour();
    expect(get).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
