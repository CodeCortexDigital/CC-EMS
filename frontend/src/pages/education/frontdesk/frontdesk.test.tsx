// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const auth = vi.hoisted(() => ({ role: 'front_desk' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: auth.role, user: { email: 'desk@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));

import api from '@/services/api';
import PickupPage from './PickupPage';
import VisitorsPage from './VisitorsPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const student = { id: 's1', student_id: 'STU001', name: 'Ava Brooks', class_name: 'Grade 5' };
const pickupList = {
  student: { id: 's1', name: 'Ava Brooks', student_id: 'STU001' },
  guardians: [
    { kind: 'guardian', id: 'g1', name: 'Erin Brooks', relationship: 'Mother', phone: '555-0100', can_pickup: true, custody_notes: '' },
    { kind: 'guardian', id: 'g2', name: 'Pete Barred', relationship: 'Father', phone: '555-0199', can_pickup: false, custody_notes: 'Court order 2025' },
  ],
  authorized_adults: [
    { kind: 'adult', id: 'a1', name: 'Uncle Joe', relationship: 'Uncle', phone: '555-0102', photo_path: '', id_type: 'Driver licence', id_checked: true, do_not_release: false, court_order_note: '' },
    { kind: 'adult', id: 'a2', name: 'Barred Bob', relationship: 'Neighbour', phone: '', photo_path: '', id_type: '', id_checked: false, do_not_release: true, court_order_note: 'Order 12' },
  ],
};

function mockApi() {
  get.mockImplementation((url: string) => {
    if (url.endsWith('/lookup/')) return Promise.resolve({ data: [student] });
    if (url.endsWith('/pickup-list/')) return Promise.resolve({ data: pickupList });
    if (url.endsWith('/pickup-releases/')) return Promise.resolve({ data: [] });
    if (url.includes('/visitors/')) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
  post.mockResolvedValue({ data: {} });
}

async function openStudent() {
  render(<PickupPage />);
  fireEvent.change(screen.getByLabelText('Find the student'), { target: { value: 'ava' } });
  fireEvent.click(await screen.findByRole('option', { name: /Ava Brooks/ }));
  await screen.findByText('Uncle Joe');
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); auth.role = 'front_desk'; mockApi(); });

describe('Pickup', () => {
  it('shows who may collect the student and who may not', async () => {
    await openStudent();
    expect(screen.getByText('Erin Brooks')).toBeTruthy();
    expect(screen.getByText('Not allowed to collect')).toBeTruthy();
    expect(screen.getByText(/Court order 2025/)).toBeTruthy();
    expect(screen.getByText('DO NOT RELEASE')).toBeTruthy();
    expect(screen.getByText(/Do not let this person take the student/)).toBeTruthy();
  });

  it('the front desk cannot override a do-not-release adult, only an administrator can', async () => {
    await openStudent();
    expect(screen.queryByText('Override…')).toBeNull();
    expect(screen.getByText(/Only an administrator can override this/)).toBeTruthy();
    cleanup();
    auth.role = 'admin';
    await openStudent();
    expect(screen.getByText('Override…')).toBeTruthy();
  });

  it('records a release only after the photo ID is confirmed', async () => {
    await openStudent();
    fireEvent.click(screen.getAllByText('Release')[0]);   // Erin Brooks
    await screen.findByLabelText(/I have checked their photo ID/);
    const confirm = screen.getAllByRole('button', { name: 'Release' }).at(-1) as HTMLButtonElement;   // the dialog's button is last
    expect(confirm.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I have checked their photo ID/));
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Dentist' } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/education/students/pickup-releases/', expect.objectContaining({
      student: 's1', guardian: 'g1', id_confirmed: true, reason: 'Dentist', early_dismissal: false,
    })));
  });

  it('an administrator override needs a typed reason before it can be sent', async () => {
    auth.role = 'admin';
    await openStudent();
    fireEvent.click(screen.getByText('Override…'));
    expect(await screen.findByRole('alert')).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/I have checked their photo ID/));
    const send = screen.getAllByRole('button', { name: 'Release' }).at(-1) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Override reason'), { target: { value: 'Order lifted, copy on file' } });
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/education/students/pickup-releases/', expect.objectContaining({
      authorized_adult: 'a2', override_reason: 'Order lifted, copy on file',
    })));
  });
});

describe('Visitors', () => {
  it('signs a visitor in, and out', async () => {
    const onSite = { id: 'v1', name: 'Pat Plumber', organisation: '', visiting: 'Office', purpose: 'Repair', badge_number: '14', checked_in_at: new Date().toISOString(), checked_out_at: null, on_site: true };
    get.mockImplementation((_url: string, cfg?: { params?: { on_site?: string } }) => Promise.resolve({ data: cfg?.params?.on_site ? [onSite] : [onSite] }));
    render(<VisitorsPage />);
    expect((await screen.findAllByText(/Pat Plumber/)).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText('Visitor name'), { target: { value: 'Sam Guest' } });
    fireEvent.change(screen.getByLabelText('Badge number'), { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/education/students/visitors/', expect.objectContaining({ name: 'Sam Guest', badge_number: '15' })));

    fireEvent.click(screen.getAllByText('Sign out')[0]);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/education/students/visitors/v1/check_out/'));
  });

  it('will not sign in a visitor without a name', async () => {
    get.mockResolvedValue({ data: [] });
    render(<VisitorsPage />);
    expect((await screen.findByRole('button', { name: 'Sign in' }) as HTMLButtonElement).disabled).toBe(true);
    expect(await screen.findByText('No visitors in the building.')).toBeTruthy();
  });
});
