// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/imports.service', () => ({
  errorText: (e: any, f: string) => e?.response?.data?.error || f,
  default: {
    kinds: vi.fn(), history: vi.fn(), previewPack: vi.fn(), importPack: vi.fn(), packExport: vi.fn(), packTemplate: vi.fn(),
    template: vi.fn(), exportKind: vi.fn(), problems: vi.fn(),
  },
}));

import imports from '@/services/imports.service';
import ImportPage from './ImportPage';

const svc = imports as unknown as Record<string, ReturnType<typeof vi.fn>>;
const KIND = (kind: string, label: string, extra = {}) => ({
  kind, label, help: `${label} help`, order: 1, file: `${kind}.csv`, depends: [], tier: 1, can_update: true, can_export: true, columns: [], last_import: null, ...extra,
});
const zip = () => new File(['PK'], 'school.zip', { type: 'application/zip' });
const pickFile = (f: File) => fireEvent.change(screen.getByLabelText('Data pack or file'), { target: { files: [f] } });

const PREVIEW = {
  file: 'school.zip', mode: 'add', committed: false, unknown_files: ['notes.txt'], order: ['classes', 'students'],
  totals: { ready: 3, update: 0, duplicate: 1, error: 1 },
  kinds: [
    { kind: 'classes', label: 'Classes and sections', file: 'classes.csv', summary: { ready: 1, update: 0, duplicate: 1, error: 0 }, rows: [], columns: [] },
    { kind: 'students', label: 'Students and guardians', file: 'students.csv', summary: { ready: 2, update: 0, duplicate: 0, error: 1 }, columns: [{ key: 'full_name', label: 'Name' }],
      rows: [{ row: 3, state: 'error', messages: ['Class "Grade 99" does not exist'], note: '', values: { full_name: 'Zed Nobody' } }] },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  svc.kinds.mockResolvedValue({ kinds: [KIND('classes', 'Classes and sections'), KIND('students', 'Students and guardians', { tier: 1 }), KIND('attendance', 'Student attendance', { tier: 2 })], max_rows: 20000 });
  svc.history.mockResolvedValue([]);
});

describe('ImportPage', () => {
  it('checks a zip pack straight away, shows what is wrong, and imports only after the button', async () => {
    svc.previewPack.mockResolvedValue(PREVIEW);
    svc.importPack.mockResolvedValue({ ...PREVIEW, committed: true });
    render(<ImportPage />);
    await screen.findByText(/Data: import, export and restore/);

    pickFile(zip());
    await waitFor(() => expect(svc.previewPack).toHaveBeenCalledWith(expect.any(File), 'add', undefined, expect.any(Function)));
    expect(await screen.findByText(/Preview: school.zip/)).toBeTruthy();
    expect(screen.getByText(/Not recognised, so skipped: notes.txt/)).toBeTruthy();
    expect(screen.getByText('Class "Grade 99" does not exist')).toBeTruthy();       // the failing kind opens by itself
    expect(svc.importPack).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Import 3 records/ }));
    await waitFor(() => expect(svc.importPack).toHaveBeenCalledWith(expect.any(File), 'add', undefined, expect.any(Function)));
  });

  it('asks what a single CSV holds before checking it, and re-checks when the mode changes', async () => {
    svc.previewPack.mockResolvedValue({ ...PREVIEW, kinds: [PREVIEW.kinds[0]], totals: { ready: 1, update: 1, duplicate: 0, error: 0 } });
    render(<ImportPage />);
    await screen.findByText(/Data: import, export and restore/);

    pickFile(new File(['a,b'], 'classes.csv', { type: 'text/csv' }));
    expect(svc.previewPack).not.toHaveBeenCalled();                                   // not until we know the kind
    fireEvent.change(await screen.findByLabelText('What this file holds'), { target: { value: 'classes' } });
    await waitFor(() => expect(svc.previewPack).toHaveBeenCalledWith(expect.any(File), 'add', 'classes', expect.any(Function)));

    fireEvent.click(screen.getByLabelText(/Add and update/));
    await waitFor(() => expect(svc.previewPack).toHaveBeenLastCalledWith(expect.any(File), 'update', 'classes', expect.any(Function)));
  });

  it('lets the office download the whole school as a pack, and a blank one', async () => {
    svc.packExport.mockResolvedValue(undefined);
    svc.packTemplate.mockResolvedValue(undefined);
    render(<ImportPage />);
    fireEvent.click(await screen.findByRole('tab', { name: /Download/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Download data pack/ }));
    await waitFor(() => expect(svc.packExport).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: /Download blank pack/ }));
    await waitFor(() => expect(svc.packTemplate).toHaveBeenCalled());
    expect(screen.getByText('Student attendance')).toBeTruthy();                       // the "during the year" files are listed too
    fireEvent.click(screen.getAllByText('Export')[0]);
    await waitFor(() => expect(svc.exportKind).toHaveBeenCalledWith('classes', 'classes.csv'));
  });
});
