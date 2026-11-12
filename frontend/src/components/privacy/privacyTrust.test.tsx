// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('@/services/privacy.service', () => ({
  errorText: (e: any, fallback: string) => e?.response?.data?.error || fallback,
  default: {
    requests: vi.fn(), updateRequest: vi.fn(), exportRequest: vi.fn(), erasePreview: vi.fn(), erase: vi.fn(),
    documents: vi.fn().mockResolvedValue({ documents: [], template: { title: '', body: '' }, history: [] }),
    consentTypes: vi.fn().mockResolvedValue([]), consentReport: vi.fn().mockResolvedValue({}),
    register: vi.fn().mockResolvedValue({ entries: [], school: '' }),
  },
}));

import api from '@/services/api';
import privacy from '@/services/privacy.service';
import { toast } from 'sonner';
import PrivacyAdminPanel from './PrivacyAdminPanel';
import RiskReviewPanel from '@/components/analytics/RiskReviewPanel';

const p = privacy as unknown as Record<string, ReturnType<typeof vi.fn>>;
const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

const request = (over = {}) => ({
  id: 'r1', kind: 'erasure', kind_label: 'Erase data', details: 'Please erase my child.', status: 'open', status_label: 'Received', student: 'Amy Alder',
  requester: 'mum@example.com', created_at: '2026-10-01', due_date: '2026-10-31', overdue: false, response: '', handled_by: '', closed_at: null,
  student_ref: 'ABC-STU0001', can_export: true, can_erase: true, ...over,
});

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('Privacy requests: copy and erasure', () => {
  const open = async (rows = [request()]) => {
    p.requests.mockResolvedValue({ results: rows, statuses: { open: 'Received', done: 'Completed', refused: 'Refused' } });
    p.documents.mockResolvedValue({ documents: [], template: { title: '', body: '' }, history: [] });
    p.consentTypes.mockResolvedValue([]);
    render(<PrivacyAdminPanel />);
    await screen.findByText(/Please erase my child/);
  };

  it('offers a download of the data and an erasure only where the request allows it', async () => {
    await open([request(), request({ id: 'r2', kind: 'correction', details: 'Fix a name', can_export: false, can_erase: false })]);
    expect(screen.getAllByText('Download their data')).toHaveLength(1);
    expect(screen.getAllByText('Erase their data…')).toHaveLength(1);
  });

  it('downloads the copy', async () => {
    p.exportRequest.mockResolvedValue(undefined);
    await open();
    fireEvent.click(screen.getByText('Download their data'));
    await waitFor(() => expect(p.exportRequest).toHaveBeenCalledWith('r1', 'ABC-STU0001'));
  });

  it('shows what will be erased first and will not erase until the student ID is typed', async () => {
    p.erasePreview.mockResolvedValue({ confirm_with: 'ABC-STU0001', preview: {
      student: { student_id: 'ABC-STU0001', name: 'Amy Alder' }, already_erased: false, becomes: 'Former student ABC-STU0001',
      removed: { 'analytics.StudentRisk': 1, 'education_attendance.StudentFaceEncoding': 1 }, kept_without_a_name: { 'education_finance.Invoice': 3 },
      also: ['Name, contact details, ID numbers, address and birth date (kept as year only) are cleared.'],
    } });
    p.erase.mockResolvedValue({ request: request({ status: 'done' }), done: {} });
    await open();
    fireEvent.click(screen.getByText('Erase their data…'));
    expect(await screen.findByText('AI risk scores: 1')).toBeTruthy();
    expect(screen.getByText('Face recognition template: 1')).toBeTruthy();
    expect(screen.getByText('Invoices: 3')).toBeTruthy();
    expect(screen.getByText(/Former student ABC-STU0001/)).toBeTruthy();
    const go = screen.getByRole('button', { name: /Erase now/ }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Type the student ID to confirm'), { target: { value: 'wrong' } });
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Type the student ID to confirm'), { target: { value: 'abc-stu0001' } });
    expect(go.disabled).toBe(false);
    fireEvent.click(go);
    await waitFor(() => expect(p.erase).toHaveBeenCalledWith('r1', 'abc-stu0001'));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });
});

describe('Review of AI risk flags', () => {
  const flag = (over = {}) => ({
    student_id: 's1', student_name: 'Amy Alder', student_roll: 'ABC-STU0001', class_name: 'Grade 6', risk_level: 'high', risk_score: 72,
    factors: { dropout_alert: 'Student shows a high dropout risk of 72.0%.' }, fee_default_risk: 10, dropout_risk: 72, needs_review: true, review: null, ...over,
  });

  it('says the score is advice, lists the reasons and counts what is waiting for a person', async () => {
    get.mockResolvedValue({ data: [flag(), flag({ student_id: 's2', student_name: 'Low One', risk_level: 'low', needs_review: false })] });
    render(<RiskReviewPanel />);
    expect(await screen.findByText('Amy Alder')).toBeTruthy();
    expect(screen.queryByText('Low One')).toBeNull();                                  // only high and critical flags are listed
    expect(screen.getByText(/1 waiting for a person/)).toBeTruthy();
    expect(screen.getByText(/not used to decide anything about a student on their own/)).toBeTruthy();
    expect(screen.getByText(/high dropout risk of 72/)).toBeTruthy();
    expect(screen.getByText('Advice only')).toBeTruthy();
  });

  it('confirming needs no reason, dismissing needs one, and the decision is sent', async () => {
    get.mockResolvedValue({ data: [flag()] });
    post.mockResolvedValue({ data: {} });
    render(<RiskReviewPanel />);
    await screen.findByText('Amy Alder');
    const dismiss = screen.getByRole('button', { name: 'Not a concern' }) as HTMLButtonElement;
    expect(dismiss.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Reason for Amy Alder'), { target: { value: 'Family on a payment plan' } });
    expect(dismiss.disabled).toBe(false);
    fireEvent.click(dismiss);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/student-predictions/s1/review/', { decision: 'dismissed', note: 'Family on a payment plan' }));
    fireEvent.click(screen.getByRole('button', { name: 'Worth acting on' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/student-predictions/s1/review/', { decision: 'confirmed', note: '' }));
  });

  it('shows who reviewed a flag, and when', async () => {
    get.mockResolvedValue({ data: [flag({ needs_review: false, review: { decision: 'dismissed', label: 'Dismissed: not a concern', note: 'On a plan', by: 'Office Admin', at: '2026-10-20T10:00:00Z' } })] });
    render(<RiskReviewPanel />);
    expect(await screen.findByText(/Dismissed: not a concern/)).toBeTruthy();
    expect(screen.getByText(/by Office Admin/)).toBeTruthy();
  });
});
