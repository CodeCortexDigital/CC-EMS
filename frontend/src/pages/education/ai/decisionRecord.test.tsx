// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

import api from '@/services/api';
import AiGovernancePage from './AiGovernancePage';

const get = api.get as unknown as ReturnType<typeof vi.fn>;

const row = {
  id: 'r1', action: 'send_fee_reminder', label: 'Send a fee reminder', summary: 'Send a fee reminder for invoice INV-7 to the family', status: 'executed',
  requested_by: 'Amy Accountant', requester_role: 'accountant', created_at: '2026-10-22T10:00:00Z', expires_at: '2026-10-24T10:00:00Z',
  decided_by: 'Head', decided_at: '2026-10-22T11:00:00Z', decision_note: 'Go ahead', result: {}, approver_roles: ['admin'], can_decide: false,
};
const record = (over = {}) => ({
  request: { ...row, arguments: { invoice_number: 'INV-7' } },
  basis: { provider: 'gemini', model: 'gemini-flash-lite-latest', instructions_sha256: 'a'.repeat(64), asked: 'Remind the family of INV-7',
    sources: [], tool_outputs_sent: [], controls: { contact_details_shared: false, use_notice_accepted: true }, recorded_at: '2026-10-22T10:00:00Z' },
  basis_sha256: 'b'.repeat(64), basis_matches_trail: true,
  trail: [
    { seq: 1, at: '2026-10-22T10:00:00Z', status: 'requested', action: 'UPDATE', by: 'amy@alder.test', data: {}, hash: 'h1', previous_hash: '' },
    { seq: 2, at: '2026-10-22T11:00:00Z', status: 'approved', action: 'UPDATE', by: 'head@alder.test', data: { note: 'Go ahead' }, hash: 'h2', previous_hash: 'h1' },
  ],
  chain: { verifies: true, records_checked: 2, problems: [], newest_hash: 'h2' },
  generated_at: '2026-10-22T12:00:00Z', note: 'The trail is tamper-evident, not tamper-proof.', ...over,
});

const open = async (rec: unknown) => {
  get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/record/') ? rec : [row] }));
  render(<AiGovernancePage />);
  fireEvent.click(await screen.findByText('Decision record'));
};

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('Decision record', () => {
  it('shows what it was based on, every step and a verified trail', async () => {
    await open(record());
    expect(await screen.findByText('The trail verifies')).toBeTruthy();
    expect(screen.getByText(/gemini \/ gemini-flash-lite-latest/)).toBeTruthy();
    expect(screen.getByText('Remind the family of INV-7')).toBeTruthy();
    expect(screen.getByText(/#1 requested/)).toBeTruthy();
    expect(screen.getByText(/#2 approved/)).toBeTruthy();
    expect(screen.getByText(/note: Go ahead/)).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/ai/governance/approvals/r1/record/');
  });

  it('says so plainly when the trail does not verify', async () => {
    await open(record({ chain: { verifies: false, records_checked: 2, problems: ['x: record 2 (ai.action.send_fee_reminder) was changed after it was written'], newest_hash: 'h2' } }));
    expect(await screen.findByText('The trail does NOT verify')).toBeTruthy();
    expect(screen.getByText(/was changed after it was written/)).toBeTruthy();
  });

  it('says so when what the request was based on no longer matches', async () => {
    await open(record({ basis_matches_trail: false }));
    expect(await screen.findByText('The trail does NOT verify')).toBeTruthy();
    expect(screen.getByText(/does not match what was recorded/)).toBeTruthy();
  });
});
