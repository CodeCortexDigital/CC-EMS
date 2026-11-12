// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const role = vi.hoisted(() => ({ current: 'admin' }));
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ role: role.current }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/security.service', () => ({ default: { logPrint: vi.fn() } }));
vi.mock('./RecordPrint', () => ({ default: ({ rec }: { rec: { student_name: string } }) => <div data-testid="record-print">{rec.student_name}</div> }));
vi.mock('@/services/recordTransfer.service', async (orig) => {
  const actual = await orig<typeof import('@/services/recordTransfer.service')>();
  return { ...actual, default: { get: vi.fn(), send: vi.fn(), issued: vi.fn(), retention: vi.fn(), dispose: vi.fn() } };
});

import recordTransfer, { RetentionRow, TransferInfo, TransferRow } from '@/services/recordTransfer.service';
import security from '@/services/security.service';
import TransferPage from './TransferPage';
import RetentionPage from './RetentionPage';

const m = recordTransfer as unknown as Record<string, ReturnType<typeof vi.fn>>;
const info = (over: Partial<TransferInfo> = {}): TransferInfo => ({
  problems: [], ready: true, transfers: [],
  retention: { left_on: null, counted_from: null, guidance_until: null, register_until: null, guidance_disposed_at: null }, ...over,
});
const sent = (over: Partial<TransferRow> | Record<string, unknown> = {}): TransferRow => ({ id: 't1', kind: 'transfer', kind_label: '転学 (写し)', to_school: '北中学校', sent_on: '2026-12-20', note: '', issued_at: '2026-12-20T10:00:00Z', issued_by: '鈴木 一郎',
                               snapshot: { student_name: '山田 太郎' } as unknown as TransferRow['snapshot'], ...over } as TransferRow);
const row = (over: Partial<RetentionRow> = {}): RetentionRow => ({
  id: 'r1', student_number: 'W-001', class_name: '3年1組', level: 'junior_high', left_on: '2018-03-15', counted_from: '2018-04-01', guidance_until: '2023-04-01',
  register_until: '2038-04-01', guidance_disposed_at: null, guidance_expired: true, register_expired: false, ...over,
});

const openTransfer = () => render(<MemoryRouter initialEntries={['/education/records/r1/transfer']}><Routes><Route path="/education/records/:id/transfer" element={<TransferPage />} /></Routes></MemoryRouter>);

beforeEach(() => { vi.clearAllMocks(); cleanup(); role.current = 'admin'; m.get.mockResolvedValue(info()); });

describe('Send the record to another school', () => {
  it('explains that the retention periods start when the pupil leaves', async () => {
    openTransfer();
    expect(await screen.findByText(/The pupil is still enrolled/)).toBeTruthy();
  });

  it('shows the retention dates once the pupil has left', async () => {
    m.get.mockResolvedValue(info({ retention: { left_on: '2027-03-15', counted_from: '2027-04-01', guidance_until: '2032-04-01', register_until: '2047-04-01', guidance_disposed_at: null } }));
    openTransfer();
    expect(await screen.findByText(/Guidance part \(指導に関する記録\): until 令和14年/)).toBeTruthy();
    expect(screen.getByText(/Register \(学籍に関する記録\): until 令和29年/)).toBeTruthy();
  });

  it('lists what stops it being sent and will not send', async () => {
    m.get.mockResolvedValue(info({ ready: false, problems: ['第2学年に校長の印がありません。'] }));
    openTransfer();
    expect(await screen.findByText('第2学年に校長の印がありません。')).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('School name'), { target: { value: '北中学校' } });
    expect(screen.getByText('Send it')).toHaveProperty('disabled', true);
  });

  it('sends it to a named school and shows the kept copy', async () => {
    m.send.mockResolvedValue(sent());
    openTransfer();
    const go = await screen.findByText('Send it');
    expect(go).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByPlaceholderText('School name'), { target: { value: '北中学校' } });
    fireEvent.click(go);
    await waitFor(() => expect(m.send).toHaveBeenCalledWith('r1', expect.objectContaining({ kind: 'transfer', to_school: '北中学校' })));
    expect(await screen.findByText('Sent copy')).toBeTruthy();
    expect(screen.getByTestId('record-print').textContent).toBe('山田 太郎');
  });

  it('can send an advance, and a teacher sees no send form', async () => {
    m.send.mockResolvedValue(sent({ kind: 'advance', kind_label: '進学 (抄本)' }));
    openTransfer();
    fireEvent.change(await screen.findByLabelText(/^Kind/), { target: { value: 'advance' } });
    fireEvent.change(screen.getByPlaceholderText('School name'), { target: { value: '第一高校' } });
    fireEvent.click(screen.getByText('Send it'));
    await waitFor(() => expect(m.send).toHaveBeenCalledWith('r1', expect.objectContaining({ kind: 'advance' })));
    cleanup();
    role.current = 'teacher';
    openTransfer();
    await screen.findByText('How long the record is kept');
    expect(screen.queryByText('Send it')).toBeNull();
  });

  it('opens a copy that was sent before and reports a print', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    m.get.mockResolvedValue(info({ transfers: [sent({ snapshot: undefined })] }));
    m.issued.mockResolvedValue(sent());
    openTransfer();
    fireEvent.click(await screen.findByText('View this copy'));
    await waitFor(() => expect(m.issued).toHaveBeenCalledWith('r1', 't1'));
    fireEvent.click(await screen.findByText('Print / PDF'));
    expect((security as any).logPrint).toHaveBeenCalledWith('records', 'r1');
    expect(print).toHaveBeenCalled();
  });
});

describe('Record retention', () => {
  const list = (over = {}) => ({ guidance_years: 5, register_years: 20, guidance_due: [row()], register_due: [], soon: [], kept: 1, ...over });

  it('lists what has passed its period and what is close', async () => {
    m.retention.mockResolvedValue(list({ soon: [row({ id: 'r2', student_number: 'W-002', guidance_expired: false })] }));
    render(<MemoryRouter><RetentionPage /></MemoryRouter>);
    expect(await screen.findByText(/W-001 · 3年1組 · left/)).toBeTruthy();
    expect(screen.getByText(/W-002 · 3年1組 · guidance until/)).toBeTruthy();
  });

  it('disposes of selected records only after the count is typed', async () => {
    m.retention.mockResolvedValue(list());
    m.dispose.mockResolvedValue({ disposed: 1, part: 'guidance' });
    render(<MemoryRouter><RetentionPage /></MemoryRouter>);
    fireEvent.click(await screen.findByLabelText('Select W-001'));
    const go = screen.getByText(/Dispose of 1 selected/);
    expect(go).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByLabelText('Type the number of records to confirm'), { target: { value: '1' } });
    expect(go).toHaveProperty('disabled', false);
    fireEvent.click(go);
    await waitFor(() => expect(m.dispose).toHaveBeenCalledWith('guidance', ['r1']));
  });

  it('says so when nothing is due', async () => {
    m.retention.mockResolvedValue(list({ guidance_due: [] }));
    render(<MemoryRouter><RetentionPage /></MemoryRouter>);
    expect((await screen.findAllByText('None.')).length).toBe(3);
  });
});
