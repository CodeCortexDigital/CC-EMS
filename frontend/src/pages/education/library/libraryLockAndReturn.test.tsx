// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }));
vi.mock('@/utils/currency', () => ({ formatMoney: (v: number) => `$${v}` }));
vi.mock('@/services/library.service', () => ({
  errorText: (e: any, fallback: string) => e?.response?.data?.error || fallback,
  default: { books: vi.fn(), book: vi.fn(), updateCopy: vi.fn(), returnBook: vi.fn(), addCopies: vi.fn(), removeBook: vi.fn() },
}));

import library from '@/services/library.service';
import LibraryCataloguePage from './LibraryCataloguePage';
import ReturnCheck from './ReturnCheck';

const lib = library as unknown as Record<string, ReturnType<typeof vi.fn>>;

const loan: any = { id: 'loan1', title: 'The Secret Garden', barcode: 'LIB-000001', member: { id: 'm1', name: 'Sara Ali', kind: 'student', card_number: 'C1' } };
const result: any = { loan: { ...loan, return_method: 'scan' }, days_late: 0, fine: 0, hold_for: null, member: {} };

beforeEach(() => { vi.clearAllMocks(); cleanup(); });

describe('Return check', () => {
  it('names the book it expects and returns it when the right barcode is scanned', async () => {
    lib.returnBook.mockResolvedValue(result);
    const onDone = vi.fn();
    render(<ReturnCheck loan={loan} onClose={() => undefined} onDone={onDone} />);
    expect(screen.getByText(/should be LIB-000001/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Barcode of the book in your hand'), { target: { value: 'LIB-000001' } });
    fireEvent.click(screen.getByRole('button', { name: 'Return' }));
    await waitFor(() => expect(lib.returnBook).toHaveBeenCalledWith('LIB-000001', { loan_id: 'loan1', manual: false }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(result));
  });

  it('a wrong book returns nothing and shows which book was scanned', async () => {
    lib.returnBook.mockRejectedValue({ response: { data: { error: 'That is "Matilda" (LIB-000009), not the book on this loan. Please scan the right book.' } } });
    const onDone = vi.fn();
    render(<ReturnCheck loan={loan} onClose={() => undefined} onDone={onDone} />);
    fireEvent.change(screen.getByLabelText('Barcode of the book in your hand'), { target: { value: 'LIB-000009' } });
    fireEvent.click(screen.getByRole('button', { name: 'Return' }));
    expect((await screen.findByRole('alert')).textContent).toMatch(/Matilda.*not the book on this loan/);
    expect(onDone).not.toHaveBeenCalled();
    expect((screen.getByLabelText('Barcode of the book in your hand') as HTMLInputElement).value).toBe('');      // ready for the next scan
  });

  it('cannot be submitted empty', () => {
    render(<ReturnCheck loan={loan} onClose={() => undefined} onDone={() => undefined} />);
    expect((screen.getByRole('button', { name: 'Return' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('a torn label can be confirmed by hand, which is sent as manual', async () => {
    lib.returnBook.mockResolvedValue({ ...result, loan: { ...result.loan, return_method: 'manual' } });
    const onDone = vi.fn();
    render(<ReturnCheck loan={loan} onClose={() => undefined} onDone={onDone} />);
    fireEvent.click(screen.getByLabelText(/will not scan/));
    expect(screen.queryByLabelText('Barcode of the book in your hand')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Return without scanning' }));
    await waitFor(() => expect(lib.returnBook).toHaveBeenCalledWith('', { loan_id: 'loan1', manual: true }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });
});

describe('Locking a copy in the safe', () => {
  const book = { id: 'b1', title: 'The Secret Garden', authors: 'F. H. Burnett', subject: 'Fiction', call_number: 'F BUR', copies: 2, available: 2, waiting: 0 };
  const copies = [
    { id: 'c1', barcode: 'LIB-000001', status: 'available', status_label: 'On the shelf', condition: 'good', location: 'A', notes: '', price: null, borrower: null, due_date: null, overdue: false },
    { id: 'c2', barcode: 'LIB-000002', status: 'locked', status_label: 'Locked in the safe', condition: 'good', location: 'A', notes: '', price: null, borrower: null, due_date: null, overdue: false,
      locked_reason: 'Rare first edition', locked_by: 'Office Admin', locked_at: '2026-10-20T10:00:00Z' },
  ];
  const open = async () => {
    lib.books.mockResolvedValue({ results: [book], subjects: ['Fiction'], can_manage: true });
    lib.book.mockResolvedValue({ ...book, copy_list: copies, queue: [], times_borrowed: 0 });
    render(<MemoryRouter><LibraryCataloguePage /></MemoryRouter>);
    fireEvent.click(await screen.findByText('F. H. Burnett'));
    await screen.findByText('LIB-000001');
  };

  it('shows why a locked copy is locked and offers to unlock it', async () => {
    await open();
    expect(screen.getByText('Locked in the safe')).toBeTruthy();
    expect(screen.getByText(/Rare first edition · Office Admin/)).toBeTruthy();
    lib.updateCopy.mockResolvedValue({});
    fireEvent.change(screen.getByLabelText('Status of LIB-000002'), { target: { value: 'available' } });
    await waitFor(() => expect(lib.updateCopy).toHaveBeenCalledWith('c2', { status: 'available' }));
  });

  it('asks for a reason before locking, and will not lock without one', async () => {
    await open();
    lib.updateCopy.mockResolvedValue({});
    fireEvent.change(screen.getByLabelText('Status of LIB-000001'), { target: { value: 'locked' } });
    const lockButton = await screen.findByRole('button', { name: 'Lock it' });
    expect((lockButton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Reason for locking'), { target: { value: '  Water damage, kept aside ' } });
    expect((lockButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(lockButton);
    await waitFor(() => expect(lib.updateCopy).toHaveBeenCalledWith('c1', { status: 'locked', reason: 'Water damage, kept aside' }));
  });

  it('a locked copy cannot be locked again (only unlocked)', async () => {
    await open();
    const options = Array.from((screen.getByLabelText('Status of LIB-000002') as HTMLSelectElement).options).map((o) => o.value);
    expect(options).not.toContain('locked');
    expect(options).toContain('available');
  });
});
