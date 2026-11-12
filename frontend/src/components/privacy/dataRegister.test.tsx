// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/privacy.service', () => ({
  errorText: (e: any, fallback: string) => e?.response?.data?.error || fallback,
  default: { register: vi.fn(), loadRegisterDefaults: vi.fn(), saveRegisterEntry: vi.fn(), deleteRegisterEntry: vi.fn(), registerCsv: vi.fn() },
}));

import privacy from '@/services/privacy.service';
import DataRegister from './DataRegister';

const p = privacy as unknown as Record<string, ReturnType<typeof vi.fn>>;
const entry = (over = {}) => ({
  id: 'e1', key: 'health', name: 'Health information', data_items: 'Allergies', purpose: 'Student safety', how_collected: 'Guardian forms',
  retention: 'While enrolled', shared_with: 'Only staff who need it', storage_location: 'Cloud servers', sensitive: true, needs_consent: true,
  is_active: true, reviewed_at: '2026-11-01T00:00:00Z', updated_by: 'Office', ...over,
});

beforeEach(() => { vi.clearAllMocks(); cleanup(); document.documentElement.lang = 'ja'; });

describe('Data handling register', () => {
  it('offers the standard list when empty, in the page language', async () => {
    p.register.mockResolvedValue({ entries: [], school: 'Wakaba' });
    p.loadRegisterDefaults.mockResolvedValue({ entries: [entry()], school: 'Wakaba' });
    render(<DataRegister />);
    fireEvent.click(await screen.findByText('Add the standard list'));
    await waitFor(() => expect(p.loadRegisterDefaults).toHaveBeenCalledWith('ja'));
    expect(await screen.findByText('Health information')).toBeTruthy();
  });

  it('flags sensitive data and data that needs consent, and shows each field', async () => {
    p.register.mockResolvedValue({ entries: [entry(), entry({ id: 'e2', name: 'Attendance', sensitive: false, needs_consent: false })], school: 'Wakaba' });
    render(<DataRegister />);
    await screen.findByText('Health information');
    expect(screen.getAllByText('Sensitive')).toHaveLength(1);
    expect(screen.getAllByText('Needs consent')).toHaveLength(1);
    expect(screen.getAllByText('Purpose of use:')).toHaveLength(2);
    expect(screen.getAllByText('Retention:').length).toBe(2);
  });

  it('edits a line and saves it', async () => {
    p.register.mockResolvedValue({ entries: [entry()], school: 'Wakaba' });
    p.saveRegisterEntry.mockResolvedValue({ entries: [entry({ retention: '5 years' })], school: 'Wakaba' });
    render(<DataRegister />);
    fireEvent.click(await screen.findByLabelText('Edit Health information'));
    fireEvent.change(screen.getByLabelText('Retention'), { target: { value: '5 years' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(p.saveRegisterEntry).toHaveBeenCalledWith(expect.objectContaining({ id: 'e1', retention: '5 years' })));
    expect(await screen.findByText('5 years')).toBeTruthy();
  });

  it('adds a line and removes one', async () => {
    p.register.mockResolvedValue({ entries: [entry()], school: 'Wakaba' });
    p.saveRegisterEntry.mockResolvedValue({ entries: [entry(), entry({ id: 'e3', name: 'Bus list' })], school: 'Wakaba' });
    p.deleteRegisterEntry.mockResolvedValue({ entries: [], school: 'Wakaba' });
    render(<DataRegister />);
    fireEvent.click(await screen.findByText('Add a line'));
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bus list' } });
    fireEvent.change(screen.getByLabelText('Purpose of use'), { target: { value: 'Bus routes' } });
    fireEvent.click(screen.getByText('Save'));
    await screen.findByText('Bus list');
    fireEvent.click(screen.getByLabelText('Edit Health information'));
    fireEvent.click(screen.getByText('Remove'));
    await waitFor(() => expect(p.deleteRegisterEntry).toHaveBeenCalledWith('e1'));
  });
});
