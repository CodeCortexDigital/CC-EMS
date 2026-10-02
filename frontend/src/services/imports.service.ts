// Data import, export and restore: one-file imports and the whole-school data pack (a zip of CSV files).
import api from './api';

export type Mode = 'add' | 'update' | 'restore';
export interface ImportKind {
  kind: string; label: string; help: string; order: number; file: string; depends: string[]; tier: number;
  can_update: boolean; can_export: boolean;
  columns: { key: string; label: string; required: boolean }[];
  last_import: { when: string; added: number } | null;
}
export type RowState = 'ready' | 'update' | 'duplicate' | 'error';
export interface PreviewRow { row: number; state: RowState; messages: string[]; note: string; values: Record<string, string> }
export interface Summary { ready: number; update: number; duplicate: number; error: number }
export interface Preview {
  file: string; mode: Mode; columns: { key: string; label: string }[]; unknown_columns: string[]; summary: Summary; rows: PreviewRow[];
}
export interface ImportResult { id: string; added: number; updated: number; skipped: number; failed: number; message: string; problems: PreviewRow[] }
export interface PackKindResult {
  kind: string; label: string; file: string; summary?: Summary; rows?: PreviewRow[]; truncated?: boolean; error?: string;
  unknown_columns?: string[]; columns?: { key: string; label: string }[]; run_id?: string; message?: string;
}
export interface PackResult {
  file: string; mode: Mode; committed: boolean; kinds: PackKindResult[]; totals: Summary; unknown_files: string[]; order: string[];
}
export interface ImportJob {
  id: string; status: 'running' | 'done' | 'failed'; file: string; commit: boolean; total_files: number; files_done: number;
  current: string; error: string; result: PackResult | null;
}
export type Progress = (job: ImportJob) => void;
export interface ImportHistoryRow {
  id: string; kind: string; label: string; file: string; mode: string; when: string; by: string;
  rows: number; added: number; updated: number; skipped: number; failed: number; has_problems: boolean;
}

const multipart = { headers: { 'Content-Type': 'multipart/form-data' } };
const form = (file: File, extra: Record<string, string> = {}) => {
  const f = new FormData();
  f.append('file', file);
  Object.entries(extra).forEach(([k, v]) => f.append(k, v));
  return f;
};

async function save(url: string, filename: string) {
  const res = await api.get(url, { responseType: 'blob' });
  const disposition = String(res.headers?.['content-disposition'] || '');
  const named = /filename="?([^";]+)"?/i.exec(disposition)?.[1];
  const href = URL.createObjectURL(res.data as Blob);
  const a = document.createElement('a');
  a.href = href; a.download = named || filename; a.click();
  URL.revokeObjectURL(href);
}

export const errorText = (e: any, fallback: string) => e?.response?.data?.error || fallback;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Big packs run on the server in the background (the answer is a job). Wait for it, telling the caller how far it is. */
async function settle(data: PackResult | { job: ImportJob }, onProgress?: Progress, every = 1500): Promise<PackResult> {
  if (!('job' in data)) return data;
  let job = data.job;
  for (;;) {
    onProgress?.(job);
    if (job.status === 'done' && job.result) return job.result;
    if (job.status === 'failed') throw { response: { data: { error: job.error || 'The import stopped.' } } };
    await sleep(every);
    job = (await api.get(`/auth/imports/pack/jobs/${job.id}/`)).data as ImportJob;
  }
}

const importsService = {
  kinds: () => api.get('/auth/imports/').then((r) => r.data as { kinds: ImportKind[]; max_rows: number }),
  template: (kind: string) => save(`/auth/imports/${kind}/template/`, `import-${kind}.csv`),
  exportKind: (kind: string, file: string) => save(`/auth/imports/${kind}/export/`, file),
  packTemplate: () => save('/auth/imports/pack/template/', 'ccems-data-pack-template.zip'),
  packExport: (kinds?: string[]) => save(`/auth/imports/pack/export/${kinds?.length ? `?kinds=${kinds.join(',')}` : ''}`, 'school-data-pack.zip'),
  previewPack: (file: File, mode: Mode, kind?: string, onProgress?: Progress) =>
    api.post('/auth/imports/pack/preview/', form(file, { mode, ...(kind ? { kind } : {}) }), multipart).then((r) => settle(r.data, onProgress)),
  importPack: (file: File, mode: Mode, kind?: string, onProgress?: Progress) =>
    api.post('/auth/imports/pack/import/', form(file, { mode, ...(kind ? { kind } : {}) }), multipart).then((r) => settle(r.data, onProgress)),
  history: () => api.get('/auth/imports/history/').then((r) => r.data.results as ImportHistoryRow[]),
  problems: (id: string, kind: string) => save(`/auth/imports/history/${id}/problems.csv`, `import-${kind}-problems.csv`),
};

export default importsService;
