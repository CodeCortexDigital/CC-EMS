// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/utils/region', () => ({ useRegion: () => ({ paymentOptions: [{ value: 'cash', label: 'Cash' }] }) }));
vi.mock('@/utils/currency', () => ({ getCurrencySymbol: () => '$', cur: () => '$' }));
vi.mock('@/services/apiEndpoints', () => ({ API_ENDPOINTS: { STUDENTS: '/students/' } }));
vi.mock('@/services/api', () => ({ default: { get: vi.fn(), post: vi.fn() }, extractListData: (d: any) => (Array.isArray(d) ? d : d?.results ?? []) }));
vi.mock('@/services/academic.service', () => ({ default: { classes: { getAll: vi.fn() } } }));
vi.mock('@/services/ledger.service', () => ({ default: {} }));
vi.mock('@/services/finance.service', () => ({ default: { getInvoices: vi.fn(), getPayments: vi.fn() } }));

import api from '@/services/api';
import academicService from '@/services/academic.service';
import financeService from '@/services/finance.service';
import InvoicesPage from './InvoicesPage';

const day = (offset: number) => { const d = new Date(); d.setDate(d.getDate() + offset); return d.toISOString().slice(0, 10); };
const inv = (n: string, over: Record<string, unknown>) => ({ id: n, invoice_number: n, student: 's1', student_name: 'Kid', amount: 100, total_amount: 100, paid_amount: 0, balance_due: 100, status: 'issued', due_date: day(-10), ...over });

const INVOICES = [
  inv('PAID-1', { paid_amount: 100, balance_due: 0, status: 'paid' }),
  inv('PART-OVERDUE', { paid_amount: 40, balance_due: 60, status: 'partial', due_date: day(-5) }),
  inv('PEND-OVERDUE-1', { due_date: day(-20) }),
  inv('PEND-OVERDUE-2', { due_date: day(-3) }),
  inv('PEND-FUTURE', { due_date: day(+15) }),
];

beforeEach(() => {
  vi.clearAllMocks(); cleanup(); localStorage.clear();
  (financeService.getInvoices as any).mockResolvedValue({ data: INVOICES });
  (financeService.getPayments as any).mockResolvedValue({ data: [] });
  (api.get as any).mockResolvedValue({ data: [] });
  (academicService.classes.getAll as any).mockResolvedValue([]);
});

const open = async () => { render(<MemoryRouter><InvoicesPage /></MemoryRouter>); await screen.findByText('PAID-1'); };
// The same words are also in the status dropdown, so take the one that is inside a card button.
const tile = (label: RegExp) => screen.getAllByText(label).map((e) => e.closest('button')).find(Boolean) as HTMLButtonElement;

describe('Invoice list, pending and defaulters', () => {
  it('the Pending card and the Pending list agree, even when every unpaid invoice is overdue', async () => {
    await open();
    const card = tile(/Pending Invoices/);
    expect(card.textContent).toContain('3');                               // three invoices with nothing paid
    fireEvent.click(card);
    await waitFor(() => expect(screen.queryByText('PAID-1')).toBeNull());
    expect(screen.getByText('PEND-OVERDUE-1')).toBeTruthy();
    expect(screen.getByText('PEND-OVERDUE-2')).toBeTruthy();
    expect(screen.getByText('PEND-FUTURE')).toBeTruthy();
    expect(screen.queryByText('PART-OVERDUE')).toBeNull();                 // partly paid is not "pending"
  });

  it('the Defaulters card counts everything past its due date with money still owed, and the list matches', async () => {
    await open();
    const card = tile(/Defaulters/);
    expect(card.textContent).toContain('3');                               // two pending and one partly paid, all overdue
    fireEvent.click(card);
    await waitFor(() => expect(screen.queryByText('PEND-FUTURE')).toBeNull());
    expect(screen.getByText('PART-OVERDUE')).toBeTruthy();
    expect(screen.getByText('PEND-OVERDUE-1')).toBeTruthy();
    expect(screen.queryByText('PAID-1')).toBeNull();
  });

  it('paid, partial and all still work', async () => {
    await open();
    fireEvent.click(tile(/Partial Paid/));
    await waitFor(() => expect(screen.queryByText('PAID-1')).toBeNull());
    expect(screen.getByText('PART-OVERDUE')).toBeTruthy();
    fireEvent.click(tile(/Paid Invoices/));
    await waitFor(() => expect(screen.getByText('PAID-1')).toBeTruthy());
    expect(screen.queryByText('PEND-FUTURE')).toBeNull();
    fireEvent.click(tile(/Total Invoices/));
    await waitFor(() => expect(screen.getByText('PEND-FUTURE')).toBeTruthy());
  });
});
