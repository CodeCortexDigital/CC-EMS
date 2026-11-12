// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/standards.service', async (orig) => {
  const actual = await orig<typeof import('@/services/standards.service')>();
  return { ...actual, default: { get: vi.fn(), saveSchoolCode: vi.fn(), ids: vi.fn(), importCsv: vi.fn(), remove: vi.fn(), exportCsv: vi.fn() } };
});

import standards from '@/services/standards.service';
import MextStandardsPage from './MextStandardsPage';

const m = standards as unknown as Record<string, ReturnType<typeof vi.fn>>;
const row = (over = {}) => ({ id: 'e1', kind: 'student', local_id: 'WKG-0001', name: '山田 太郎', system: '教育委員会', external_id: 'S-1', ...over });

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  m.get.mockResolvedValue({ school_code: '', systems: [] });
  m.ids.mockResolvedValue({ results: [], systems: [] });
});

describe('MEXT standards page', () => {
  it('saves the school code', async () => {
    m.saveSchoolCode.mockResolvedValue({ school_code: 'B113110000012' });
    render(<MextStandardsPage />);
    const field = await screen.findByLabelText('School code');
    expect(screen.getByText('Save the code')).toHaveProperty('disabled', true);
    fireEvent.change(field, { target: { value: 'b113110000012' } });
    fireEvent.click(screen.getByText('Save the code'));
    await waitFor(() => expect(m.saveSchoolCode).toHaveBeenCalledWith('b113110000012'));
    expect(await screen.findByText('Saved')).toBeTruthy();
  });

  it('shows a refused code in the words the server gave', async () => {
    const { toast } = await import('sonner');
    m.saveSchoolCode.mockRejectedValue({ response: { data: { school_code: 'The MEXT school code is a letter and twelve digits.' } } });
    render(<MextStandardsPage />);
    fireEvent.change(await screen.findByLabelText('School code'), { target: { value: '123' } });
    fireEvent.click(screen.getByText('Save the code'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('The MEXT school code is a letter and twelve digits.'));
  });

  it('imports pasted rows for a named system and lists what was saved', async () => {
    m.importCsv.mockResolvedValue({ results: [row()], systems: ['教育委員会'], saved: 1, errors: [] });
    render(<MextStandardsPage />);
    const go = await screen.findByText('Import');
    expect(go).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByPlaceholderText(/教育委員会 校務支援システム/), { target: { value: '教育委員会' } });
    fireEvent.change(screen.getByLabelText(/^Rows/), { target: { value: 'student,WKG-0001,S-1' } });
    fireEvent.click(go);
    await waitFor(() => expect(m.importCsv).toHaveBeenCalledWith('教育委員会', 'student,WKG-0001,S-1'));
    expect(await screen.findByText('S-1')).toBeTruthy();
    expect(screen.getByText('山田 太郎')).toBeTruthy();
  });

  it('lists the rows that were not saved, with the reason', async () => {
    m.importCsv.mockResolvedValue({ results: [], systems: ['X'], saved: 0, errors: [{ row: 2, message: 'No student with the ID NOPE.' }] });
    render(<MextStandardsPage />);
    fireEvent.change(await screen.findByPlaceholderText(/教育委員会 校務支援システム/), { target: { value: 'X' } });
    fireEvent.change(screen.getByLabelText(/^Rows/), { target: { value: 'student,NOPE,1' } });
    fireEvent.click(screen.getByText('Import'));
    expect(await screen.findByText(/Row 2: No student with the ID NOPE\./)).toBeTruthy();
  });

  it('removes an id', async () => {
    m.ids.mockResolvedValue({ results: [row()], systems: ['教育委員会'] });
    m.remove.mockResolvedValue({ results: [], systems: [] });
    render(<MextStandardsPage />);
    fireEvent.click(await screen.findByLabelText('Remove S-1'));
    await waitFor(() => expect(m.remove).toHaveBeenCalledWith('e1', undefined));
    expect(await screen.findByText(/No IDs saved/)).toBeTruthy();
  });
});
