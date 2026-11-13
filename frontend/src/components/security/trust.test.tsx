// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/security.service', () => ({
  default: {
    selfAssessment: vi.fn(), answerAssessment: vi.fn(), downloadAssessment: vi.fn(),
    timestamps: vi.fn(), stampNow: vi.fn(), downloadStamp: vi.fn(),
  },
}));

import { toast } from 'sonner';
import security from '@/services/security.service';
import TrustPanel from './TrustPanel';

const s = security as unknown as Record<string, ReturnType<typeof vi.fn>>;

const assessment = (over: Record<string, unknown> = {}) => ({
  disclaimer: 'This is the school\'s own checklist. It is not an audit.',
  generated_at: '2026-11-13T00:00:00Z',
  summary: { met: 1, partly: 0, open: 2, total: 3 },
  items: [
    { key: 'register', area: 'What is held', text: 'A register says what personal information is held.', status: 'met', evidence: '13 lines in the data handling register.', source: 'system' },
    { key: 'timestamp', area: 'Keeping it intact', text: 'The trail is time-stamped by an outside authority.', status: 'open', evidence: 'No time-stamping authority is set up on the server.', source: 'system' },
    { key: 'officer', area: 'Organisation', text: 'A person is named as responsible for personal information.', status: 'open', evidence: 'Not answered yet.', source: 'school', answer: '' },
  ],
  ...over,
});
const stamps = (over: Record<string, unknown> = {}) => ({
  enabled: true, authority: 'https://tsa.example/stamp', records: 5, newest_hash: 'ab'.repeat(32), up_to_date: false, how_to_check: 'openssl ts -verify ...',
  chain: { ok: true, problems: [] }, stamps: [], ...over,
});

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  s.selfAssessment.mockResolvedValue(assessment());
  s.timestamps.mockResolvedValue(stamps());
});

describe('Self-assessment', () => {
  it('shows the disclaimer, the totals, the lines by area and what the system found', async () => {
    render(<TrustPanel />);
    expect(await screen.findByText(/It is not an audit/)).toBeTruthy();
    expect(screen.getByLabelText('Summary').textContent).toMatch(/1 met, 0 partly, 2 open of 3/);
    expect(screen.getByText('What is held')).toBeTruthy();
    expect(screen.getByText('13 lines in the data handling register.')).toBeTruthy();
    expect(screen.getAllByText('Open').length).toBe(2);
  });

  it('only the lines the school must answer have an answer box', async () => {
    render(<TrustPanel />);
    await screen.findByText(/It is not an audit/);
    expect(screen.getAllByRole('combobox').length).toBe(1);
  });

  it('answering sends the answer with its note and shows the new result', async () => {
    s.answerAssessment.mockResolvedValue(assessment({
      summary: { met: 2, partly: 0, open: 1, total: 3 },
      items: [...assessment().items.slice(0, 2), { key: 'officer', area: 'Organisation', text: 'A person is named as responsible for personal information.', status: 'met', evidence: 'Ms Sato', source: 'school', answer: 'yes', answered_by: 'head@a.test' }],
    }));
    render(<TrustPanel />);
    fireEvent.change(await screen.findByLabelText(/Answer: A person is named/), { target: { value: 'yes' } });
    await waitFor(() => expect(s.answerAssessment).toHaveBeenCalledWith('officer', 'yes', ''));
    expect(await screen.findByText(/Ms Sato \(head@a.test\)/)).toBeTruthy();
    expect(screen.getByLabelText('Summary').textContent).toMatch(/2 met/);
  });

  it('says why when an answer could not be saved', async () => {
    s.answerAssessment.mockRejectedValue({ response: { data: { error: 'Answer yes, partly or no.' } } });
    render(<TrustPanel />);
    fireEvent.change(await screen.findByLabelText(/Answer: A person is named/), { target: { value: 'yes' } });
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Answer yes, partly or no.'));
  });

  it('downloads the CSV', async () => {
    s.downloadAssessment.mockResolvedValue(undefined);
    render(<TrustPanel />);
    fireEvent.click(await screen.findByText('CSV'));
    expect(s.downloadAssessment).toHaveBeenCalled();
  });
});

describe('Outside time stamps', () => {
  it('says nothing is sent while no authority is set up', async () => {
    s.timestamps.mockResolvedValue(stamps({ enabled: false, authority: '' }));
    render(<TrustPanel />);
    expect(await screen.findByText(/No time-stamping authority is set up on the server yet/)).toBeTruthy();
    expect(screen.queryByText('Time-stamp now')).toBeNull();
  });

  it('stamps now and then lists the stamp with its signed reply', async () => {
    const stamped = stamps({ up_to_date: true, stamps: [{ id: 's1', seq: 5, hash: 'ab'.repeat(32), authority: 'https://tsa.example/stamp', at: '2026-11-13T09:00:00Z' }] });
    s.stampNow.mockResolvedValue(stamped);
    s.downloadStamp.mockResolvedValue(undefined);
    render(<TrustPanel />);
    fireEvent.click(await screen.findByText('Time-stamp now'));
    await waitFor(() => expect(s.stampNow).toHaveBeenCalled());
    expect(await screen.findByText(/The newest record is time-stamped/)).toBeTruthy();
    fireEvent.click(screen.getByText('Signed reply'));
    expect(s.downloadStamp).toHaveBeenCalledWith('s1', 5);
  });

  it('shows a trail that does not check out', async () => {
    s.timestamps.mockResolvedValue(stamps({ chain: { ok: false, problems: ['x: record 3 (ai.settings.test) was changed after it was written'] } }));
    render(<TrustPanel />);
    expect(await screen.findByText('The trail does not check out.')).toBeTruthy();
    expect(screen.getByText(/record 3 .* was changed/)).toBeTruthy();
  });

  it('explains a refusal from the authority', async () => {
    s.stampNow.mockRejectedValue({ response: { data: { error: 'The time-stamping authority could not be reached: down' } } });
    render(<TrustPanel />);
    fireEvent.click(await screen.findByText('Time-stamp now'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('The time-stamping authority could not be reached: down'));
  });
});
