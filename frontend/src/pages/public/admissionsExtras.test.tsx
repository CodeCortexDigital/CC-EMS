// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));
vi.mock('@/services/admission.service', () => ({ default: { list: vi.fn().mockResolvedValue({ results: [] }) } }));

import api from '@/services/api';
import ApplicationPortalPage from './ApplicationPortalPage';
import WaitlistTab from '@/components/admissions/WaitlistTab';
import { ChecklistPanel, FeePanel } from '@/components/admissions/ApplicationExtras';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const inFuture = (h: number) => new Date(Date.now() + h * 3600_000).toISOString();
let offerOpen = true;

function familyApi() {
  get.mockImplementation((url: string) => {
    if (url.endsWith('/public/offer/')) return Promise.resolve({ data: { application_no: 'APP-1', student: 'Maya Brooks', grade: 'Grade 5', status: 'waitlisted', offer: offerOpen ? { id: 'o1', expires_at: inFuture(48) } : null } });
    if (url.endsWith('/public/fee/')) return Promise.resolve({ data: { fee: { amount: '25.00', currency: 'USD', status: 'unpaid' } } });
    if (url.endsWith('/public/documents/')) return Promise.resolve({ data: { items: [
      { name: 'Birth certificate', state: 'missing', document: null, note: '' },
      { name: 'Report card', state: 'redo', document: { id: 'd1', name: 'r.pdf', url: '/r.pdf' }, note: 'Wrong year' },
      { name: 'Photo', state: 'received', document: { id: 'd2', name: 'p.png', url: '/p.png' }, note: '' }] } });
    if (url.endsWith('/public/tours/')) return Promise.resolve({ data: { slots: [{ id: 'sl1', kind: 'tour', starts_at: inFuture(72), ends_at: inFuture(73), location: 'Front office', host: 'Ms Lee', capacity: 2, is_open: true, booked: 0, seats_left: 2 }], my_bookings: [] } });
    return Promise.resolve({ data: [] });
  });
  post.mockResolvedValue({ data: { status: 'approved', items: [] } });
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); offerOpen = true; familyApi(); });

const renderPortal = (q = '?no=APP-1&token=tok') => render(<MemoryRouter initialEntries={[`/apply/manage${q}`]}><ApplicationPortalPage /></MemoryRouter>);

describe('Family application page', () => {
  it('asks for the number and tracking code when the link does not carry them', () => {
    renderPortal('');
    expect((screen.getByRole('button', { name: 'Open my application' }) as HTMLButtonElement).disabled).toBe(true);
    expect(get).not.toHaveBeenCalled();
  });

  it('says so plainly when the code is wrong', async () => {
    get.mockRejectedValue({ response: { status: 404 } });
    renderPortal();
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText(/could not find an application/)).toBeTruthy();
  });

  it('shows an open seat offer with its deadline, and accepting sends the family code', async () => {
    renderPortal();
    expect(await screen.findByText(/A place is available for Maya Brooks/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Accept the place' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/public/offer/', { no: 'APP-1', token: 'tok', decision: 'accept' }));
  });

  it('shows no offer card when there is no open offer', async () => {
    offerOpen = false;
    renderPortal();
    await screen.findByText('Maya Brooks');
    expect(screen.queryByText(/A place is available/)).toBeNull();
  });

  it('shows the fee, the document checklist, and sends a file for a missing or sent-back document', async () => {
    renderPortal();
    expect(await screen.findByText('Not paid yet')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Pay by card' })).toBeTruthy();
    expect(await screen.findByText(/The school asked: Wrong year/)).toBeTruthy();
    expect(screen.queryByLabelText('Upload Photo')).toBeNull();                 // already received: nothing to send
    const file = new File(['%PDF'], 'birth.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('Upload Birth certificate'), { target: { files: [file] } });
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/public/documents/', expect.any(FormData), expect.anything()));
    const form = post.mock.calls.find((c) => String(c[0]).endsWith('/public/documents/'))![1] as FormData;
    expect(form.get('doc_type')).toBe('Birth certificate');
    expect(form.get('token')).toBe('tok');
  });

  it('books a tour time', async () => {
    renderPortal();
    fireEvent.click(await screen.findByRole('button', { name: 'Book this time' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/public/tours/', { no: 'APP-1', token: 'tok', slot: 'sl1' }));
  });
});

describe('Admissions staff panels', () => {
  it('the waiting list shows seats free, and offering seats is one click', async () => {
    get.mockImplementation((url: string) => {
      if (url.endsWith('/waitlist-configs/')) return Promise.resolve({ data: [{ id: 'c1', class_name: 'Grade 5', academic_year: '2026-2027', capacity: 3, offer_hours: 72, sibling_priority: true, staff_child_priority: true, seats_taken: 2, open_offers: 0, seats_left: 1, waiting: 4 }] });
      return Promise.resolve({ data: [] });
    });
    post.mockResolvedValue({ data: { offers_made: 1 } });
    render(<WaitlistTab defaultYear="2026-2027" />);
    expect(await screen.findByText('1 seat free')).toBeTruthy();
    expect(screen.getByText(/3 in total · 2 taken · 0 offered · 4 waiting/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Offer free seats' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/waitlist-configs/c1/fill/'));
  });

  it('sending a document back needs a reason; marking it received does not', async () => {
    get.mockResolvedValue({ data: { complete: false, items: [{ name: 'Birth certificate', state: 'uploaded', document: { id: 'd1', name: 'b.pdf', url: '/b.pdf' }, note: '' }] } });
    render(<ChecklistPanel applicationId="app1" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Send again…' }));
    const ask = screen.getByRole('button', { name: 'Ask the family' }) as HTMLButtonElement;
    expect(ask.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('What to send again'), { target: { value: 'Too blurry' } });
    fireEvent.click(ask);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/applications/app1/documents/d1/review/', { status: 'redo', note: 'Too blurry' }));
  });

  it('an unpaid fee puts the application on hold, and waiving it needs a reason', async () => {
    const changed = vi.fn();
    render(<FeePanel applicationId="app1" fee={{ amount: '25.00', currency: 'USD', status: 'unpaid' }} onChanged={changed} />);
    expect(screen.getByText(/Unpaid: application is on hold/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Waive' }));
    const go = screen.getByRole('button', { name: 'Waive fee' }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Reason for waiving'), { target: { value: 'Staff child' } });
    fireEvent.click(go);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/auth/admissions/applications/app1/fee/waive/', { note: 'Staff child' }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
  });

  it('shows nothing for an application without a fee', () => {
    const { container } = render(<FeePanel applicationId="app1" fee={null} onChanged={() => undefined} />);
    expect(container.firstChild).toBeNull();
  });
});
