// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

import api from '@/services/api';
import TrailRecords from './TrailRecords';

const get = api.get as unknown as ReturnType<typeof vi.fn>;

const entries = [
  { seq: 7, at: '2026-11-05T10:00:00Z', kind: 'answer', kind_label: 'Assistant answer', by: 'Head', summary: 'Asked: How many students are absent?', resource_id: 'm1', resource_type: 'ai.chat.answer' },
  { seq: 6, at: '2026-11-05T09:00:00Z', kind: 'risk', kind_label: 'Risk flag review', by: 'Head', summary: 'Confirmed for a student flagged high', resource_id: 's1', resource_type: 'analytics.risk.review' },
];
const detail = (verifies = true) => ({
  ...entries[0], data: { answer: '12 students', basis: { asked: 'How many students are absent?' } }, previous_data: null, hash: 'abc123', previous_hash: 'zzz999',
  chain: { verifies, records_checked: 7, problems: verifies ? [] : ['Record 5 was changed'], newest_hash: 'abc123' },
  generated_at: '2026-11-05T12:00:00Z', note: 'The trail is tamper-evident, not tamper-proof.',
});

beforeEach(() => {
  get.mockReset();
});
afterEach(cleanup);

describe('Decision records tab', () => {
  it('lists answers and risk reviews, filters by kind, and opens one with its hashes', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/7/') ? detail() : entries }));
    render(<TrailRecords />);
    expect(await screen.findByText('Asked: How many students are absent?')).toBeTruthy();
    expect(screen.getByText('Confirmed for a student flagged high')).toBeTruthy();

    fireEvent.click(screen.getByText('Risk flag reviews'));
    await waitFor(() => expect(get).toHaveBeenCalledWith(expect.stringContaining('/records/'), { params: { kind: 'risk' } }));

    fireEvent.click((await screen.findAllByText('Open'))[0]);
    expect(await screen.findByText('The trail verifies')).toBeTruthy();
    expect(screen.getByText(/abc123/)).toBeTruthy();
  });

  it('says plainly when the trail does not verify', async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.endsWith('/7/') ? detail(false) : entries }));
    render(<TrailRecords />);
    fireEvent.click((await screen.findAllByText('Open'))[0]);
    expect(await screen.findByText('The trail does NOT verify')).toBeTruthy();
    expect(screen.getByText('Record 5 was changed')).toBeTruthy();
  });
});
