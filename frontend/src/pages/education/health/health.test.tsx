// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: 'nurse', user: { email: 'nora@school.test' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => (Array.isArray(d) ? d : (d as { results?: unknown[] })?.results ?? []),
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), put: vi.fn() },
}));

import api from '@/services/api';
import HealthOfficePage from './HealthOfficePage';
import ParentHealthPage from '@/pages/portals/parent/ParentHealthPage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const student = { id: 's1', student_id: 'STU001', name: 'Ava Brooks', class_name: 'Grade 5' };
const medication = {
  id: 'm1', student: 's1', student_name: 'Ava Brooks', medication_name: 'Ibuprofen', dose: '200 mg', route: 'oral', times: '12:00',
  min_hours_between_doses: 6, start_date: '2026-09-01', end_date: null, instructions: '', prescriber: '', parent_consent: true,
  parent_consent_on: '2026-09-01', is_active: true, is_current: true,
};
const visit = { id: 'v1', student: 's1', student_name: 'Ava Brooks', time_in: '2026-10-02T10:00:00Z', time_out: null, visit_type: 'illness', complaint: 'Headache', action_taken: 'rested', action_notes: '', sent_home: false, temperature: null, recorded_by_name: 'Nora Nurse', parent_notified_at: '2026-10-02T10:05:00Z' };

function mockApi() {
  get.mockImplementation((url: string) => {
    if (url.endsWith('/lookup/')) return Promise.resolve({ data: [student] });
    if (url.endsWith('/health-visits/')) return Promise.resolve({ data: [visit] });
    if (url.endsWith('/medication-authorizations/')) return Promise.resolve({ data: [medication] });
    return Promise.resolve({ data: [] });
  });
  post.mockResolvedValue({ data: {} });
}

beforeEach(() => { vi.clearAllMocks(); cleanup(); mockApi(); });

describe('Health office', () => {
  it('lists visits, and a new visit needs a student first', async () => {
    render(<HealthOfficePage />);
    expect(await screen.findByText('Headache')).toBeTruthy();
    expect(screen.getByText('parent told')).toBeTruthy();
    expect((screen.getByRole('button', { name: /New visit/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('records a visit for the chosen student', async () => {
    render(<HealthOfficePage />);
    fireEvent.change(screen.getByLabelText('Find a student'), { target: { value: 'ava' } });
    fireEvent.click(await screen.findByRole('option', { name: /Ava Brooks/ }));
    await waitFor(() => expect((screen.getByRole('button', { name: /New visit/ }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: /New visit/ }));
    fireEvent.change(await screen.findByLabelText('Complaint'), { target: { value: 'Scraped knee' } });
    fireEvent.change(screen.getByLabelText('Action taken'), { target: { value: 'treated' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save visit' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/education/students/health-visits/', expect.objectContaining({ student: 's1', complaint: 'Scraped knee', action_taken: 'treated', sent_home: false })));
  });

  it('a dose that is too soon asks for a reason, then goes through with it', async () => {
    post.mockRejectedValueOnce({ response: { data: { override_reason: ['A dose was given 120 minutes ago and at least 6 hours are needed between doses. Type a reason to give it anyway.'] } } });
    render(<HealthOfficePage />);
    fireEvent.click(screen.getByRole('tab', { name: 'Medication' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Give dose' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Record dose' }));

    expect(await screen.findByText(/Too soon/)).toBeTruthy();
    const again = screen.getByRole('button', { name: 'Give anyway' }) as HTMLButtonElement;
    expect(again.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Reason for giving it early'), { target: { value: 'Fever spiked, parent approved by phone' } });
    expect(again.disabled).toBe(false);
    fireEvent.click(again);
    await waitFor(() => expect(post).toHaveBeenLastCalledWith('/education/students/medication-logs/', expect.objectContaining({
      authorization: 'm1', status: 'given', override_reason: 'Fever spiked, parent approved by phone',
    })));
  });

  it('only offers "Give dose" for a current permission', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/medication-authorizations/') ? [{ ...medication, parent_consent: false, is_current: false }] : [] }));
    render(<HealthOfficePage />);
    fireEvent.click(screen.getByRole('tab', { name: 'Medication' }));
    expect(await screen.findByText('waiting for parent consent')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Give dose' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Consent received' })).toBeTruthy();
  });
});

describe('Parent health page', () => {
  it('is read only: visits and medication, no way to change them', async () => {
    render(<ParentHealthPage />);
    expect(await screen.findByText('Headache')).toBeTruthy();
    expect(screen.getByText('Ibuprofen')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
